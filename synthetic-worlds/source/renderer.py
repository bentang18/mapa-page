"""v11 candidate observation prior. Offline synthesis only; no model training.

Continuous 64s interior plus 8s voltage context at both ends. Fit the actual
lower-median/MAD frontend normalizer on the first 24s; reserve 8s before the
32s content interval. Complete availability; no clinical artifacts/anatomy.
Frequency-dependent voltage mixing precedes canonical CAR/filter/periodic-Hann
STFT. Widths are extra tile kernels, not cortical millimeters. The inherited
carrier also has a sampled 0.3–0.75-tile blur. Both coupling arms use identical
control-computed spatial RMS scales and the sampled-arm prefix normalizer.
This candidate is a testable engineering prior, not identified neurophysiology.
"""
import hashlib,json,time
import numpy as np
import torch
from frontend import (interp_fine,delayed,filtered,phase_r2,affine_parameters,normalize,CONTEXT,FS,FPS,N,SOURCES,SessionRobustZNormalizer)
from scipy.ndimage import gaussian_filter,gaussian_filter1d
from scipy.signal import butter,hilbert,sosfiltfilt
from frontend import ar_field,contextual_switching,_single_stft_raw_view_chunked


def spectral_weights(n):
    f=np.fft.rfftfreq(n,1/FS)
    def rise(lo,hi):
        q=np.clip((f-lo)/(hi-lo),0,1)
        return .5-.5*np.cos(np.pi*q)
    a=rise(14,18);b=rise(56,64)
    return np.stack([1-a,a-b,b])


def split_spectrum(x):
    spec=np.fft.rfft(x,axis=0)
    return [np.fft.irfft(spec*w[:,None],n=len(x),axis=0).astype('f4') for w in spectral_weights(len(x))]


def spatial_matrix(rows,cols,sigma):
    d2=(rows[:,None]-rows[None,:])**2+(cols[:,None]-cols[None,:])**2
    matrix=np.exp(-d2/(2*sigma*sigma))
    return (matrix/np.sqrt((matrix*matrix).sum(1,keepdims=True))).astype('f4')


def spatial_voltage(x,rows,cols):
    result=np.zeros_like(x)
    for part,sigma in zip(split_spectrum(x),[1.1,1.1,.65]):
        mixed=part@spatial_matrix(rows,cols,sigma).T
        mixed*=np.sqrt(np.mean(part.astype('f8')**2)/max(1e-20,np.mean(mixed.astype('f8')**2)))
        result+=mixed
    return result


def source_drives_long(rng,h,w,*,core,total_frames,shared_weight):
    # Sample one recurrent rule, then evolve it continuously through all context.
    total = total_frames
    if core is not None:
        history, core_hidden, core_params = core(rng,h,w)
        assert history.shape[0] == total and np.isfinite(history).all()
        k=history.shape[-1]
        if 'regime' in core_hidden:
            regimes=core_hidden['regime']
            gate_basis='native switching regimes'
        else:
            # A renderer gate, not a claim that a continuous core has regimes.
            first=history[:,0] if history.ndim==2 else history[...,0].mean(axis=(1,2))
            regimes=np.digitize(normalize(first),[-.5,.5])
            gate_basis='three bins of standardized first coordinate (spatial mean for local core), thresholds -0.5/+0.5; renderer interaction gate only'
        retained={f'core_{name}':value for name,value in core_hidden.items()}
        retained['core_parameters_json']=np.asarray(json.dumps(core_params))
        retained['interaction_gate_basis']=np.asarray(gate_basis)
    else:
        history, regimes, retained = contextual_switching(rng,h,w,total)
        k=history.shape[-1]
    rr,cc=np.mgrid[:h,:w]
    times=np.arange(total)/FPS-CONTEXT
    fields=[];maps=[];weights=[];params=[]
    widths=[(.6,2.2),(1.5,4.5),(1.5,4.5),(2,5),(.6,2.4)]
    taus=[(.06,.3),(.3,.9),(.2,.7),(.08,.3),(.05,.18)]
    for source in range(5):
        spatial=[]
        for j in range(k):
            cy,cx=rng.uniform(0,h),rng.uniform(0,w);sigma=rng.uniform(*widths[source])
            patch=np.exp(-((rr-cy)**2+(cc-cx)**2)/(2*sigma*sigma))
            spatial.append(patch)
        spatial=np.asarray(spatial); weight=rng.normal(size=k)
        if history.ndim==2:
            shared=normalize(np.einsum('tk,k,khw->thw',history,weight,spatial,optimize=True))
        else:
            # Pointwise channel readout retains the local core's spatial state.
            shared=normalize(np.einsum('thwk,k,khw->thw',history,weight,spatial,optimize=True))
        tau_source=float(rng.uniform(*taus[source]))
        local=ar_field(rng,total,h,w,tau_source,float(rng.uniform(.4,1.3)))
        field=shared_weight*shared+(1-shared_weight)*local
        if source:
            pulses=np.zeros((total,h,w))
            for _ in range(int(total/FPS*rng.uniform(1,2.5))):
                onset=int(rng.integers(total)); cy,cx=rng.uniform(0,h),rng.uniform(0,w)
                sigma=rng.uniform(*widths[source]);spot=np.exp(-((rr-cy)**2+(cc-cx)**2)/(2*sigma*sigma))
                duration=float(rng.uniform(*taus[source]));dt=np.arange(total-onset)/FPS
                pulse=(1-np.exp(-dt/max(.025,duration/4)))*np.exp(-dt/duration)
                pulses[onset:]+=rng.uniform(.8,2.0)*pulse[:,None,None]*spot
            field+=pulses
        fields.append(field); maps.append(spatial); weights.append(weight)
        params.append({'source':SOURCES[source],'envelope_tau_s':tau_source,'width_range_cells':list(widths[source]),'pulse_rate_range_hz':[1,2.5]})
    retained.update(source_maps=np.asarray(maps),source_weights=np.asarray(weights))
    return np.asarray(fields), history, regimes, times, retained, params


def features_long(voltage,frames):
    wave=torch.from_numpy(voltage.T.copy());start=CONTEXT*FPS;result=[]
    for length,lo,hi in [(1024,1,7),(256,2,7),(128,4,10)]:
        x=_single_stft_raw_view_chunked(wave,sample_rate=FS,nperseg=length,hop_length=64,k0=lo,k1=hi,log_eps=1e-6,chunk_frames=64)
        result.append(x[...,start:start+frames].contiguous())
    return result


def spatial_voltage_recipe(x,rows,cols,widths,scales=None):
    result=np.zeros_like(x);used=[]
    for b,(part,sigma) in enumerate(zip(split_spectrum(x),widths)):
        mixed=part@spatial_matrix(rows,cols,sigma).T
        factor=np.sqrt(np.mean(part.astype('f8')**2)/max(1e-20,np.mean(mixed.astype('f8')**2))) if scales is None else scales[b]
        result+=mixed*factor;used.append(float(factor))
    return result,used


def generate(seed, entry, real, *, core, settings, duration_s=64, calibration_s=24, calibration=None):
    started=time.monotonic();rng=np.random.default_rng(seed)
    N=int(duration_s*FPS);calibration_frames=int(calibration_s*FPS)
    assert calibration_s==24 and duration_s==64
    spatial=True;distinct=True;flat_hf=False;freeze_hga=False;no_harmonic=False;carrier_only=False
    gain_strength=settings['hga_gain']
    contacts=entry['contacts'];r0=min(c['source_row'] for c in contacts);c0=min(c['source_col'] for c in contacts)
    rows=np.asarray([c['source_row']-r0 for c in contacts]);cols=np.asarray([c['source_col']-c0 for c in contacts])
    h,w=int(rows.max()+1),int(cols.max()+1);c=len(contacts)
    fields,state,regime,time32,hidden,source_params=source_drives_long(rng,h,w,core=core,total_frames=int((duration_s+2*CONTEXT)*FPS),shared_weight=settings["shared_core_weight"])
    rawtime=np.arange((duration_s+2*CONTEXT)*FS)/FS-CONTEXT
    centers=CONTEXT*FS+np.arange(N)*64; frame_slice=slice(CONTEXT*FPS,(CONTEXT+duration_s)*FPS)
    sampled=fields[:,:,rows,cols]
    fine=[interp_fine(q,time32,rawtime) for q in sampled]
    exponent=float(rng.uniform(2,3.5));knee=float(rng.uniform(8,25))
    # One colored realization spans the spectrum; rhythms are added to it.
    white=rng.standard_normal((len(rawtime),h,w),dtype=np.float32)
    white=gaussian_filter(white,sigma=(0,float(rng.uniform(.3,.75)),float(rng.uniform(.3,.75))),mode='reflect')[:,rows,cols]
    freq=np.fft.rfftfreq(len(rawtime),1/FS)
    color=(1+(freq/knee)**2)**(-exponent/4);color[0]=0
    carrier=np.fft.irfft(np.fft.rfft(white,axis=0)*color[:,None],n=len(rawtime),axis=0).astype('f4')
    carrier/=carrier.std()+1e-8
    hidden['white_innovations_sha256']=np.asarray(hashlib.sha256(white.tobytes()).hexdigest())
    hidden['original_carrier_sha256']=np.asarray(hashlib.sha256(carrier.tobytes()).hexdigest())
    if flat_hf:
        old_high=split_spectrum(carrier)[2]
        new_high=split_spectrum(white)[2]
        new_high*=np.sqrt(np.mean(old_high.astype('f8')**2)/np.mean(new_high.astype('f8')**2))
        carrier=carrier-old_high+new_high
    del white
    base_broad=np.exp(.65*np.tanh(fine[0]))
    frequencies=[];phases=[];oscillations=[];source_amplitudes=[None]
    for j,(lo,hi) in enumerate([(4,7),(8,12),(17,28),(33,52)],1):
        center=float(rng.uniform(lo,hi));jitter=gaussian_filter1d(rng.normal(size=len(time32)),6)
        inst=center+.12*normalize(jitter)
        phase0=2*np.pi*np.cumsum(np.interp(rawtime,time32,inst))/FS
        spatial_gradient=rng.uniform(-.25,.25,2)
        spatial_phase=rows*spatial_gradient[0]+cols*spatial_gradient[1]+rng.normal(0,.08,c)
        phase=(phase0[:,None]+spatial_phase).astype('f4');phases.append(phase)
        harmonic=float(rng.uniform(0,.12)) if j==4 else 0.
        oscillations.append(np.cos(phase)+harmonic*np.cos(2*phase))
        # Distinct, burst-prone envelopes; finite shared task input remains in null.
        envelope=.12+np.logaddexp(0,1.5*fine[j]-.8)
        source_amplitudes.append(envelope.astype('f4'))
        frequencies.append({'source':SOURCES[j],'carrier_center_hz':center,'second_harmonic':harmonic,'spatial_phase_gradient':spatial_gradient.tolist()})
    nreg=int(regime.max()+1)
    regional=normalize(gaussian_filter(rng.normal(size=(h,w)),1.8))[rows,cols]
    beta_coeff=rng.uniform(-.65,.65,nreg)*settings["beta_scale"];beta_coeff[0]=0
    beta_map=beta_coeff[regime][:,None]*np.tanh(.7*regional[None,:]+.5)
    lag=int(rng.integers(0,5));beta_mod32=beta_map*np.tanh(delayed(sampled[0],lag))
    beta_mod=interp_fine(beta_mod32,time32,rawtime)
    theta_strength=float(rng.uniform(.2,.55));theta_strength=settings["theta_pac"]
    strength32=theta_strength*(.45+.55*(regime%3)/2)[:,None]*(.65+.35*np.tanh(regional))[None,:]
    strength=interp_fine(strength32,time32,rawtime)
    preferred=float(rng.uniform(-np.pi,np.pi))
    pac_gate=strength*np.cos(phases[0]-preferred)
    # Exact paired intervention: only these two terms differ between arms.
    gain_contact=np.exp(rng.normal(0,.15,c))
    source_levels=np.asarray([1.,.75,.4,.35,.22])*np.exp(rng.normal(0,.15,5))
    # Complementary spectral partition of the SAME carrier; no new random draws.
    # The intervention changes only which existing source gain drives each part.
    carrier_parts=split_spectrum(carrier)
    broad_gains=[base_broad]*3
    if distinct:
        broad_gains=[np.exp(.65*np.tanh(.25*fine[0]+np.sqrt(1-.25**2)*fine[j])) for j in [1,3]]+[base_broad]
    # Intervention preserves the same trajectory/innovations and never speeds
    # the core clock. Gain freezing is a negative control, not a proposed prior.
    if freeze_hga:
        constant=np.exp(np.log(broad_gains[2]).mean(0,keepdims=True))
        broad_gains[2]=np.broadcast_to(constant,broad_gains[2].shape).copy()
    elif gain_strength!=.65:
        broad_gains[2]=np.exp(gain_strength*np.tanh(fine[0]))
    # Weak broad, slow shared gain: an explicit population-level observation
    # prior. Its coefficient is sampled, not fitted as a biological fraction.
    coordinate=state[:,0] if state.ndim==2 else state[...,0].mean(axis=(1,2))
    slow_common=normalize(gaussian_filter1d(coordinate,8))
    common=interp_fine(slow_common[:,None],time32,rawtime)
    broad_gains[2]*=np.exp(settings['broad_gain']*np.tanh(common))
    if no_harmonic:
        oscillations[3]=np.cos(phases[3])
    if carrier_only:
        broad_gains=[np.ones_like(g) for g in broad_gains]
        source_amplitudes=[None]+[np.zeros_like(source_amplitudes[j]) for j in range(1,5)]
        pac_gate=np.zeros_like(pac_gate);beta_mod=np.zeros_like(beta_mod)
    broad_voltage=sum(g*x for g,x in zip(broad_gains,carrier_parts))
    baseline=(broad_voltage*source_levels[0]).astype('f4') if distinct else base_broad*carrier*source_levels[0]
    for j in range(1,5):baseline+=source_levels[j]*source_amplitudes[j]*oscillations[j-1]
    delta=(np.exp(pac_gate)-1)*broad_voltage*source_levels[0] if distinct else (np.exp(pac_gate)-1)*base_broad*carrier*source_levels[0]
    delta+=(np.exp(beta_mod)-1)*source_levels[3]*source_amplitudes[3]*oscillations[2]
    control=(baseline*gain_contact).astype('f4');coupled=((baseline+delta)*gain_contact).astype('f4')
    if spatial:
        control,spatial_scales=spatial_voltage_recipe(control,rows,cols,settings["spatial_sigma_cells"])
        coupled,_=spatial_voltage_recipe(coupled,rows,cols,settings["spatial_sigma_cells"],scales=spatial_scales)
    hidden['aperiodic_component_gain']=np.stack([g[centers] for g in broad_gains]).astype('f4')
    hidden['pre_measurement_carrier_sha256']=np.asarray(hashlib.sha256(carrier.tobytes()).hexdigest())
    noise_rms=float(rng.uniform(.08,.2));noise=noise_rms*rng.standard_normal(control.shape,dtype=np.float32)
    # Shared linear filter/noise path, identical across both arms.
    filtered_control=filtered(control);filtered_coupled=filtered(coupled);filtered_noise=filtered(noise)
    del control,coupled,baseline,delta,noise,carrier,fine
    clean_bins=[features_long(filtered_coupled,N),features_long(filtered_control,N)]
    noisy_bins=[features_long(filtered_coupled+filtered_noise,N),features_long(filtered_control+filtered_noise,N)]
    theta_phase=phases[0][centers]
    stft_phase_curves=[];raw_r2=[]
    for voltage in [filtered_coupled,filtered_control]:
        high=sosfiltfilt(butter(4,[64,160],fs=FS,btype='bandpass',output='sos'),voltage,axis=0)
        amplitude=abs(hilbert(high,axis=0))[centers]
        raw_r2.append(phase_r2(amplitude,theta_phase))
    # Known source gains at frame centers, before CAR/filter/STFT. Not expected magnitude.
    control_sources=np.stack([broad_gains[2][centers]]+[source_amplitudes[j][centers] for j in range(1,5)])
    coupled_sources=control_sources.copy();coupled_sources[0]*=np.exp(pac_gate[centers]);coupled_sources[3]*=np.exp(beta_mod[centers])
    source_values=np.stack([coupled_sources,control_sources]).astype('<f4')
    values=[];bins_saved={};scalers=[]
    drives=[np.stack([coupled_sources[1],coupled_sources[3],coupled_sources[0]]),
            np.stack([control_sources[1],control_sources[3],control_sources[0]])]
    for arm in range(2):
        norm_observed=[];norm_clean=[]
        for b in range(3):
            norm=SessionRobustZNormalizer().fit(noisy_bins[0][b][...,:calibration_frames])
            if calibration is not None:
                norm.median=torch.from_numpy(calibration[f'control_bin_median_{b}'].copy())
                norm.sigma=torch.from_numpy(calibration[f'control_bin_scale_{b}'].copy())
            ob=norm.transform(noisy_bins[arm][b]);cl=norm.transform(clean_bins[arm][b])
            norm_observed.append(ob.mean(dim=1).T.numpy());norm_clean.append(cl.mean(dim=1).T.numpy())
            bins_saved[f'arm{arm}_normalized_bins_{b}']=ob.permute(2,0,1).numpy()
            bins_saved[f'arm{arm}_raw_bins_{b}']=noisy_bins[arm][b].permute(2,0,1).numpy()
            if arm==0:
                bins_saved[f'control_bin_median_{b}']=norm.median.numpy();bins_saved[f'control_bin_scale_{b}']=norm.sigma.numpy()
        values.extend([drives[arm],np.asarray(norm_observed),np.asarray(norm_clean)])
        stft_phase_curves.append(phase_r2(norm_observed[2],theta_phase))
    values=np.asarray(values,dtype='<f4')
    drive_map=affine_parameters(values[3],real) if real is not None else None;observation_map=affine_parameters(values[4],real) if real is not None else None
    mapping=[drive_map,observation_map,observation_map]*2
    # Source displays use one reference transform per source, shared across arms.
    med=np.median(control_sources,axis=(1,2));mad=1.4826*np.median(abs(control_sources-med[:,None,None]),axis=(1,2))
    hidden.update(state=state[frame_slice].astype('f4'),regime=regime[frame_slice],
        theta_phase=theta_phase.astype('f4'),beta_interaction_log_gain=beta_mod[centers],
        theta_pac_log_gain=pac_gate[centers],source_levels=source_levels,
        source_display_median=med,source_display_scale=mad,
        component_driver=sampled[:,frame_slice].astype('f4'))
    params={'dimensions':int(state.shape[-1]),'aperiodic_exponent':exponent,'aperiodic_knee_hz':knee,
        'theta_pac_log_strength':theta_strength,'preferred_theta_phase':preferred,
        'beta_coefficients_by_regime':beta_coeff.tolist(),'beta_delay_frames':lag,
        'source_parameters':source_params,'oscillators':frequencies,'source_voltage_levels':source_levels.tolist(),
        'added_voltage_noise_rms':noise_rms,'intervention':'theta PAC gate and beta amplitude interaction only; same exogenous sources, contact maps, carrier/noise realizations, filters and scalers'}
    params['renderer_refinement']={'spatial':spatial,'distinct':distinct,'spatial_sigma_cells':settings['spatial_sigma_cells'],
        'spectral_transition_hz':[[14,18],[56,64]],'shared_gain_coefficient':.25,
        'calibration':'external frozen prefix fit' if calibration is not None else 'sampled interaction-arm first24s, frozen across arms'}
    params['temporal_intervention']={'flat_hf':flat_hf,'freeze_hga':freeze_hga,'no_harmonic':no_harmonic,'carrier_only':carrier_only,'gain_strength':gain_strength}
    params['recipe_settings']=settings
    params['session']={'duration_s':duration_s,'calibration_s':calibration_s,'content_s':32,'gap_s':8,'normalizer_fit_arm':0,'normalizer_fit_frames':[0,calibration_frames],'content_frames':[32*FPS,N],'context_each_side_s':CONTEXT,'paired_spatial_scales':'control computed once and frozen across interaction arms'}
    if core is not None:
        params['core']=json.loads(str(hidden['core_parameters_json']))
        params['interaction_gate_basis']=str(hidden['interaction_gate_basis'])
    diagnostic={'raw_hga_phase_r2':raw_r2,'stft_hga_phase_r2':stft_phase_curves,
        'interpretation':'Descriptive phase association with known theta source, not recovered from Slow magnitudes or evidence of neural causation.',
        'slow_magnitude_phase_r2':[phase_r2(values[a*3+1,0],theta_phase) for a in range(2)]}
    return values,source_values,hidden,bins_saved,params,mapping,diagnostic,[h,w],[r0,c0],time.monotonic()-started

