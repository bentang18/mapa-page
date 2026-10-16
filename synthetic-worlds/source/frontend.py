"""Canonical frontend functions and unchanged renderer support functions."""
from __future__ import annotations
import numpy as np
import torch
import mne
from scipy.ndimage import gaussian_filter,gaussian_filter1d
from cores import normalize,switching,affine_parameters
FS=2048
FPS=32
N=512
CONTEXT=8
SOURCES=["Broadband","Theta","Alpha","Beta","Low gamma"]
def _single_stft_raw_view(
    waveform: torch.Tensor,
    *,
    sample_rate: int,
    nperseg: int,
    hop_length: int,
    k0: int,
    k1: int,
    log_eps: float,
    apply_log: bool = False,
    cartesian: bool = False,
) -> torch.Tensor:
    """2STFT single-band raw |STFT| (§3a): ONE Hann STFT, keep the inclusive
    rfft-bin slice ``[k0, k1]``. ``cartesian=True`` (3STFT slow band, §4) instead
    returns the two real components stacked on the freq axis ([Re ++ Im], F →
    2·n_bins) to preserve phase; magnitude/log are bypassed.

    Same STFT call as :func:`_multi_stft_raw_view` (``center=True``,
    ``normalized=False``, value axis = raw ``|STFT|``) — only the bin selection
    differs. Input ``(..., C, T_samples)`` → output ``(..., C, k1-k0+1, T_bin)``
    with ``T_bin = 1 + T_samples // hop_length``.
    """
    win = torch.hann_window(nperseg, device=waveform.device)
    wf = waveform
    if wf.shape[-1] < nperseg:
        # NeuralSet's prepare() probes with sub-second inputs — pad so
        # torch.stft(center=True) can reflect-pad without crashing. Real
        # 1 s windows never hit this branch.
        wf = torch.nn.functional.pad(wf, (0, nperseg - wf.shape[-1]))
    spec = torch.stft(
        wf,
        n_fft=nperseg,
        hop_length=hop_length,
        win_length=nperseg,
        window=win,
        return_complex=True,
        normalized=False,
        center=True,
    )
    band = spec[..., k0 : k1 + 1, :]  # (..., n_bins, T) complex
    if cartesian:
        # Phase-bearing slow band (§4): two real channels stacked on the freq
        # axis as [Re of n_bins ++ Im of n_bins] → F doubles to 2·n_bins. Keeps
        # phase; apply_log is rejected for cartesian upstream so it never applies.
        return torch.cat([band.real, band.imag], dim=-2)  # (..., 2·n_bins, T)
    mag = band.abs()  # (..., n_bins, T)
    if apply_log:
        return torch.log(mag + log_eps)
    return mag

def _single_stft_raw_view_chunked(
    waveform: torch.Tensor,
    *,
    sample_rate: int,
    nperseg: int,
    hop_length: int,
    k0: int,
    k1: int,
    log_eps: float,
    apply_log: bool = False,
    cartesian: bool = False,
    chunk_frames: int = 960,
) -> torch.Tensor:
    """Memory-bounded whole-recording single-band raw |STFT|, byte-identical to
    one un-chunked :func:`_single_stft_raw_view` over the full ``waveform``.

    The single-band analog of :func:`_multi_stft_raw_view_chunked`: overlap-save
    in ``chunk_frames``-wide output blocks, each reading ``half = nperseg // 2``
    extra REAL samples of context per side, then keeping only the frames whose
    full analysis window was real (the ``center=True`` reflect frames survive
    only at the TRUE recording ends, exactly as the un-chunked call produces).

    Correctness needs ``half`` to be a multiple of ``hop_length`` so every
    segment starts on the global hop grid — true for both 2STFT bands
    (low 256 = 1·256; high 64 = 1·64). Pinned by the acceptance test.

    Input ``(..., C, T_samples)`` → ``(..., C, k1-k0+1, T_bin)`` with
    ``T_bin = 1 + T_samples // hop_length``.
    """
    if hop_length <= 0 or nperseg % hop_length != 0:
        raise ValueError(
            f"chunked single-band STFT needs nperseg ({nperseg}) divisible by "
            f"hop_length ({hop_length}) so segment starts land on the hop grid"
        )
    half = nperseg // 2
    if half % hop_length != 0:
        raise ValueError(
            f"chunked single-band STFT needs half=nperseg//2 ({half}) divisible "
            f"by hop_length ({hop_length}) for segment→global frame alignment"
        )
    n_samples = int(waveform.shape[-1])
    total_frames = 1 + n_samples // hop_length

    def _view(seg: torch.Tensor) -> torch.Tensor:
        return _single_stft_raw_view(
            seg,
            sample_rate=sample_rate,
            nperseg=nperseg,
            hop_length=hop_length,
            k0=k0,
            k1=k1,
            log_eps=log_eps,
            apply_log=apply_log,
            cartesian=cartesian,
        )

    # Whole recording fits in one pass (or is too short to chunk): direct call.
    if total_frames <= chunk_frames or n_samples <= 2 * half + nperseg:
        return _view(waveform)

    blocks: list[torch.Tensor] = []
    f = 0
    while f < total_frames:
        f_end = min(f + chunk_frames, total_frames)
        lo = max(0, (f * hop_length) - half)
        hi = min(n_samples, (f_end - 1) * hop_length + half + 1)
        if hi - lo < nperseg:
            lo = ((max(0, hi - nperseg)) // hop_length) * hop_length
        seg = waveform[..., lo:hi]
        spec_seg = _view(seg)
        g0 = f - lo // hop_length
        g1 = f_end - lo // hop_length
        blocks.append(spec_seg[..., g0:g1])
        f = f_end
    return torch.cat(blocks, dim=-1)

SCALE_TO_SIGMA=1.4826
class SessionRobustZNormalizer:
    """Fit each contact/bin on a complete session, then reuse the frozen statistics.

    This scaler does not identify artifacts or clip normalized values.
    """

    def __init__(self, *, sigma_floor: float = 1e-6) -> None:
        self.sigma_floor = sigma_floor
        self.median: torch.Tensor | None = None
        self.sigma: torch.Tensor | None = None
        self._valid_bin_mask: torch.Tensor | None = None

    @classmethod
    def from_stats(
        cls,
        *,
        median: torch.Tensor,
        sigma: torch.Tensor,
        sigma_floor: float = 1e-6,
        valid_bin_mask: torch.Tensor | None = None,
    ) -> SessionRobustZNormalizer:
        obj = cls(sigma_floor=sigma_floor)
        obj.median, obj.sigma = median, sigma
        obj._valid_bin_mask = valid_bin_mask
        return obj

    def fit(
        self, frames: torch.Tensor, *, valid_bin_mask: torch.Tensor | None = None,
    ) -> SessionRobustZNormalizer:
        x = (
            frames
            if frames.dtype in (torch.float16, torch.float32, torch.float64)
            else frames.float()
        )
        self.median = x.median(dim=-1, keepdim=True).values
        self.sigma = SCALE_TO_SIGMA * (x - self.median).abs().median(dim=-1, keepdim=True).values
        self._valid_bin_mask = valid_bin_mask
        return self

    def transform(self, x: torch.Tensor) -> torch.Tensor:
        if self.median is None or self.sigma is None:
            raise RuntimeError("SessionRobustZNormalizer.transform called before fit()")
        x = x if x.dtype in (torch.float16, torch.float32, torch.float64) else x.float()
        z = (x - self.median) / self.sigma.clamp(min=self.sigma_floor)
        z = torch.where(self.sigma >= self.sigma_floor, z, torch.zeros_like(z))
        if self._valid_bin_mask is not None:
            z = torch.where(self._valid_bin_mask.to(dtype=torch.bool), z, torch.zeros_like(z))
        return z

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        return self.transform(x)
def interp_fine(x, time32, rawtime):
    return np.stack([np.interp(rawtime, time32, x[:,i]) for i in range(x.shape[1])], axis=1).astype('f4')

def delayed(x, lag):
    return x.copy() if lag == 0 else np.concatenate([np.repeat(x[:1],lag,axis=0),x[:-lag]])

def ar_field(rng, frames, h, w, tau, sigma):
    innovations = gaussian_filter(rng.normal(size=(frames+96,h,w)),sigma=(0,sigma,sigma),mode='reflect')
    innovations /= innovations.std()+1e-8
    a = np.exp(-1/(FPS*tau)); z = np.zeros((h,w)); history=[]
    for i in range(frames+96):
        z=a*z+np.sqrt(1-a*a)*innovations[i]
        if i>=96: history.append(z.copy())
    return np.asarray(history)

def contextual_switching(rng,h,w,total):
    """Original v2 trajectory, preserved for exact replay of earlier outputs."""
    z0, h0, p0 = switching(rng,h,w)
    # A single world's core dimensions must stay fixed; use the first network's
    # graph and patterns to evolve the entire contextual trajectory below.
    k=z0.shape[1]; graph=h0['graph']; tau=h0['tau_s']; patterns=h0['patterns']; trans=h0['transition']
    z=np.zeros(k); regime=0; left=0; history=[]; regimes=[]
    for t in range((total+96)*4):
        if left<=0:
            regime=int(rng.choice(len(patterns),p=trans[regime]));left=int(rng.uniform(.12,.65)*128)
        left-=1; z+=(-z+np.tanh(graph@z+patterns[regime]))/(128*tau)+.018*rng.normal(size=k)
        if t>=384 and t%4==0: history.append(z.copy());regimes.append(regime)
    return np.asarray(history),np.asarray(regimes),{'graph':graph,'tau_s':tau,'patterns':patterns,'transition':trans}

def filtered(x):
    """Actual producer filter calls; all displayed samples have full FIR context."""
    x=x.T.astype('f8');x-=x.mean(axis=0,keepdims=True)
    x=mne.filter.notch_filter(x,FS,np.arange(60.,301.,60.),phase='zero',filter_length='auto',verbose=False)
    x=mne.filter.filter_data(x,FS,.5,None,verbose=False)
    return x.T.astype('f4')

def phase_r2(x, phase):
    scores=[]
    for i in range(x.shape[1]):
        design=np.stack([np.ones(len(x)),np.cos(phase[:,i]),np.sin(phase[:,i])],axis=1)
        y=x[:,i];prediction=design@np.linalg.lstsq(design,y,rcond=None)[0]
        scores.append(float(max(0,1-np.sum((y-prediction)**2)/(np.sum((y-y.mean())**2)+1e-12))))
    return {'median':float(np.median(scores)),'per_contact':scores}
