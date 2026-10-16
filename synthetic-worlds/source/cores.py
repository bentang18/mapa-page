"""Numerical cores extracted verbatim from the audited v11 implementation."""
import numpy as np
from scipy.ndimage import gaussian_filter,gaussian_filter1d
from scipy.special import expit,softmax
N=512
FPS=32
FS=2048
def normalize(x):
    return (x - x.mean()) / (x.std() + 1e-8)

def vector_standard(x):
    return (x - x.mean(axis=0, keepdims=True)) / (x.std(axis=0, keepdims=True) + 1e-6)

def sampled_graph(rng, k):
    density = float(rng.uniform(.12, .35))
    graph = rng.normal(size=(k, k)) * (rng.random((k, k)) < density)
    np.fill_diagonal(graph, 0)
    radius = float(rng.uniform(.65, 1.25))
    graph *= radius / max(float(np.max(abs(np.linalg.eigvals(graph)))), 1e-5)
    return graph, density, radius

def switching(rng, h, w, *, frames=N):
    k = int(rng.integers(12, 25))
    graph, density, radius = sampled_graph(rng, k)
    tau = np.exp(rng.uniform(np.log(.06), np.log(.5), k))
    nr = int(rng.integers(4, 9))
    patterns = rng.normal(0, .8, (nr, k))
    transition = rng.dirichlet(np.ones(nr), size=nr)
    z = rng.normal(0, .1, k)
    regime, remaining = 0, 0
    history, states, drives = [], [], []
    dt = 1 / 128
    for t in range((frames + 96) * 4):
        if remaining <= 0:
            regime = int(rng.choice(nr, p=transition[regime]))
            remaining = int(rng.uniform(.12, .65) / dt)
        remaining -= 1
        drive = patterns[regime]
        z += dt / tau * (-z + np.tanh(graph @ z + drive)) + .018 * rng.normal(size=k)
        if t >= 96 * 4 and t % 4 == 0:
            history.append(z.copy()); states.append(regime); drives.append(drive)
    return np.asarray(history), {'graph': graph, 'tau_s': tau, 'patterns': patterns,
                                'transition': transition, 'regime': np.asarray(states),
                                'external_drive': np.asarray(drives)}, {
        'dimensions': k, 'regimes': nr, 'graph_density': density,
        'graph_spectral_radius': radius, 'tau_range_s': [float(tau.min()), float(tau.max())]}

def local_field(rng, h, w, *, frames=N):
    k = int(rng.integers(4, 9))
    mix = rng.normal(size=(k, k))
    mix *= rng.uniform(.45, .95) / max(float(np.max(abs(np.linalg.eigvals(mix)))), 1e-5)
    tau = np.exp(rng.uniform(np.log(.05), np.log(.3), k))
    diffusion = rng.uniform(.08, .35, k)
    advection = rng.uniform(-.18, .18, k)
    z = rng.normal(0, .12, (h, w, k)); drive = np.zeros((h, w, k))
    rr, cc = np.mgrid[:h, :w]
    history, pulse_trace = [], []
    pulse_mix = rng.normal(size=(4, k))
    for t in range((frames + 96) * 4):
        drive *= np.exp(-1 / 128 / .13)
        if rng.random() < .025:
            y, x = rng.uniform(0, h), rng.uniform(0, w)
            width = rng.uniform(.6, 2.8)
            spot = np.exp(-((rr-y)**2 + (cc-x)**2) / (2*width**2))
            drive += spot[..., None] * pulse_mix[int(rng.integers(4))] * rng.uniform(.8, 1.8)
        pad = np.pad(z, ((1, 1), (1, 1), (0, 0)), mode='reflect')
        near = (pad[:-2, 1:-1] + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]) / 4
        lap = near-z
        grad = (pad[1:-1, 2:]-pad[1:-1, :-2])/2
        target = np.tanh(.72*z + near @ mix + diffusion*lap + advection*grad + drive)
        z += (target-z) / (128*tau) + .008*rng.normal(size=z.shape)
        if t >= 96*4 and t % 4 == 0:
            history.append(z.copy()); pulse_trace.append(float(abs(drive).mean()))
    return np.asarray(history), {'mix': mix, 'tau_s': tau, 'diffusion': diffusion,
                                'advection': advection, 'pulse_mix': pulse_mix,
                                'pulse_strength': np.asarray(pulse_trace)}, {
        'dimensions': k, 'hidden_shape': [h, w, k], 'boundary': 'reflective',
        'tau_range_s': [float(tau.min()), float(tau.max())]}

def oscillator(rng, h, w, *, frames=N):
    k = int(rng.integers(12, 25))
    graph = rng.uniform(0, 1, (k, k)) * (rng.random((k, k)) < .2)
    np.fill_diagonal(graph, 0)
    graph /= np.maximum(graph.sum(axis=1, keepdims=True), 1)
    freq = np.exp(rng.uniform(np.log(.6), np.log(7), k))
    growth = rng.uniform(-.4, .8, k)
    coupling = float(rng.uniform(.25, 1.1))
    z = .2 * (rng.normal(size=k) + 1j*rng.normal(size=k))
    forcing = np.zeros(k, dtype=complex); history, pulse_trace = [], []
    dt = 1/256
    for t in range((frames+96)*8):
        forcing *= np.exp(-dt/.16)
        if rng.random() < .012:
            forcing += rng.normal(0, .8, k) * np.exp(1j*rng.uniform(0, 2*np.pi, k))
        def derivative(q):
            return (growth+2j*np.pi*freq-abs(q)**2)*q + coupling*(graph@q-q) + forcing
        a = derivative(z); b = derivative(z+dt*a/2)
        c = derivative(z+dt*b/2); d = derivative(z+dt*c)
        z += dt*(a+2*b+2*c+d)/6 + .003*(rng.normal(size=k)+1j*rng.normal(size=k))
        if t >= 96*8 and t % 8 == 0:
            history.append(z.copy()); pulse_trace.append(float(abs(forcing).mean()))
    complex_state = np.asarray(history)
    return np.concatenate([complex_state.real, complex_state.imag], axis=1), {
        'graph': graph, 'frequency_hz': freq, 'growth': growth,
        'pulse_strength': np.asarray(pulse_trace)}, {
        'dimensions': 2*k, 'oscillators': k, 'coupling': coupling,
        'frequency_range_hz': [float(freq.min()), float(freq.max())]}

def kernel_graph(rng, h, w, *, frames=N):
    k, roots = int(rng.integers(12, 25)), int(rng.integers(5, 11))
    t = np.arange(frames) / FPS
    z = np.zeros((frames, k)); graph = np.zeros((k, k)); ops = []
    scales = np.exp(rng.uniform(np.log(.05), np.log(1.5), roots))
    for j, scale in enumerate(scales):
        omega = rng.normal(0, 1/scale, 32)
        if j % 2:
            omega[:16] = 2*np.pi*rng.uniform(.4, 4)*rng.integers(1, 4, 16) + rng.normal(0, .15, 16)
        phase = rng.uniform(0, 2*np.pi, 32); weights = rng.normal(size=32)
        z[:, j] = np.cos(t[:, None]*omega+phase) @ weights / np.sqrt(16)
        z[:, j] += rng.normal(0, .25)*(t-t.mean())/16
    for j in range(roots, k):
        parents = rng.choice(j, size=min(j, int(rng.integers(2, 5))), replace=False)
        weights = rng.normal(0, 1/np.sqrt(len(parents)), len(parents))
        graph[j, parents] = weights
        x = z[:, parents] @ weights; op = int(rng.integers(3)); ops.append(op)
        z[:, j] = np.tanh(x) if op == 0 else np.sin(x) if op == 1 else np.tanh(x)*np.tanh(z[:, parents[0]])
    return z, {'graph': graph, 'root_timescale_s': scales,
               'operations': np.asarray(ops)}, {'dimensions': k, 'roots': roots,
               'root_timescale_range_s': [float(scales.min()), float(scales.max())]}

def affine_parameters(raw, real):
    scales, offsets = [], []
    for b in range(3):
        med, target = np.median(raw[b]), np.median(real[b])
        mad = np.median(abs(raw[b]-med))
        scale = float(np.median(abs(real[b]-target))/(mad+1e-8))
        scales.append(scale); offsets.append(float(target-scale*med))
    return {'scale': scales, 'offset': offsets}
def linear(rng,h,w,*,frames=1024):
    k=16;dt=1/32;tau=np.exp(rng.uniform(np.log(.05),np.log(2),k))
    q=np.linalg.qr(rng.normal(size=(k,k)))[0];a=np.exp(-dt/tau)
    matrix=(q*a)@q.T;innovation=q*np.sqrt(1-a*a)
    x=rng.normal(size=k);history=[]
    for _ in range(frames):
        x=matrix@x+innovation@rng.normal(size=k);history.append(x.copy())
    return np.asarray(history),{'matrix':matrix,'innovation_factor':innovation,'tau_s':tau},{'dimensions':k,'tau_range_s':[float(tau.min()),float(tau.max())],'stationary_covariance':'identity','transition':'exact OU discretization'}

def rslds(rng,h,w,*,frames=1024):
    k=16;nr=4;centers=rng.normal(0,.65,(nr,k));basis=np.linalg.qr(rng.normal(size=(k,k)))[0]
    rates=rng.uniform(.80,.96,(nr,k));matrices=np.array([(basis*a)@basis.T for a in rates])
    directions=centers-np.roll(centers,1,axis=0);directions/=np.linalg.norm(directions,axis=1)[:,None]
    thresholds=np.sum(centers*directions,1)-.35
    x=centers[0]+rng.normal(0,.2,k);mode=0;history=[];modes=[];hazards=[]
    uniforms=rng.random(frames+96);noise=rng.normal(0,.025,(frames+96,k))
    for t in range(frames+96):
        logits=np.full(nr,-5.);logits[mode]=0.
        logits[(mode+1)%nr]=8*(directions[mode]@x-thresholds[mode])
        p=softmax(logits);hazard=float(p[(mode+1)%nr]);mode=min(nr-1,int(np.searchsorted(np.cumsum(p),uniforms[t])))
        x=centers[mode]+matrices[mode]@(x-centers[mode])+noise[t]
        if t>=96:history.append(x.copy());modes.append(mode);hazards.append(hazard)
    return np.asarray(history),{'matrices':matrices,'centers':centers,'switch_directions':directions,'thresholds':thresholds,'regime':np.asarray(modes),'next_mode_probability':np.asarray(hazards)}, {'dimensions':k,'regimes':nr,'transition_slope':8.,'alternative_logit':-5.,'spectral_radius_range':[float(rates.min()),float(rates.max())],'transition':'softmax, continuous-state-dependent, no imposed dwell duration'}

def ei(rng,h,w,*,frames=1024,substeps=8):
    dt=1/(32*substeps);tau_e=float(rng.uniform(.03,.07));tau_i=float(rng.uniform(.06,.14));tau_a=float(rng.uniform(.5,1.5))
    assert dt/min(tau_e,tau_i,tau_a)<.14
    e=rng.uniform(.03,.08,(h,w));i=rng.uniform(.03,.08,(h,w));adapt=e.copy();drive=np.zeros((h,w))
    rr,cc=np.mgrid[:h,:w];history=[];pulse_trace=[];inputs=[]
    # Time-continuous predetermined stimuli, so integration refinement uses
    # identical input events rather than changing random draws per solver step.
    duration=(frames+96)/32
    event_times=np.cumsum(rng.exponential(.6,size=int(duration*4)))
    events=[]
    for t in event_times:
        if t>duration:break
        y,x=rng.uniform(0,h),rng.uniform(0,w);sigma=float(rng.uniform(.6,1.7))
        events.append((float(t),float(rng.uniform(1.8,3.2)),np.exp(-((rr-y)**2+(cc-x)**2)/(2*sigma*sigma))))
    for t in range((frames+96)*substeps):
        seconds=t*dt;drive=np.zeros((h,w))
        for onset,amp,spot in events:
            age=seconds-onset
            if 0<=age<2:drive+=amp*(1-np.exp(-age/.025))*np.exp(-age/.12)*spot
        ee=gaussian_filter(e,.7,mode='reflect');ii=gaussian_filter(i,1.8,mode='reflect')
        te=expit(10*ee-12*ii-2.5-2*adapt+.8+drive)
        ti=expit(10*ee-2*ii-3.)
        e=e+dt/tau_e*(te-e);i=i+dt/tau_i*(ti-i);adapt=adapt+dt/tau_a*(e-adapt)
        if t>=96*substeps and t%substeps==0:
            history.append(np.stack([e,i,adapt],axis=-1));pulse_trace.append(float(drive.mean()));inputs.append(drive.copy())
    state=np.asarray(history);assert np.isfinite(state).all() and state.min()>=0 and state.max()<=1
    return state,{'tau_s':np.array([tau_e,tau_i,tau_a]),'pulse_strength':np.asarray(pulse_trace),'external_drive':np.asarray(inputs)}, {'dimensions':3,'hidden_shape':[h,w,3],'channels':['Excitatory','Inhibitory','Adaptation'],'tau_s':[tau_e,tau_i,tau_a],'boundary':'reflective','external_events':len(events),'mechanism':'bounded E/I sigmoid feedback with slow adaptation; not a physical voltage model'}
BASE={'switching':switching,'local':local_field,'oscillator':oscillator,'kernel':kernel_graph}
EXTRA={'linear':linear,'rslds':rslds,'ei':ei}
CORES=dict(BASE,**EXTRA)
