"""Mathematical 2D Fourier Series & Frequency-Domain Image Enhancement.

Implements research-backed algorithms:
1. 2D Fourier Homomorphic High-Frequency Emphasis (HFE) - Gonzalez & Woods:
   Separates illumination L(x, y) from reflectance R(x, y) in the Fourier domain:
     ln(I) = ln(L) + ln(R)
     Z(u, v) = F{ln(I)}
     H(u, v) = gamma_L + gamma_H * (1 - exp(-D(u,v)^2 / (2 * D0^2)))
   Compresses low-frequency dynamic range (shadows/glare) and boosts
   high-frequency object edges & micro-textures for distant objects.

2. Spectral Residual Saliency - Hou & Zhang (CVPR 2007):
   Pops out distant, anomalous objects by subtracting the averaged log-amplitude
   spectrum from the Fourier phase representation.

3. Elliptic Fourier Descriptors (EFD) - Kuhl & Giardina (1982):
   Represents object contours via closed 1D Fourier series harmonics for
   scale-, translation-, and rotation-invariant shape verification.
"""

from __future__ import annotations

import cv2
import numpy as np


class FourierHomomorphicFilter:
    """Hardware-accelerated 2D Discrete Fourier Transform (cv2.dft) High-Frequency Emphasis."""

    def __init__(
        self,
        height: int = 480,
        width: int = 640,
        gamma_l: float = 0.75,
        gamma_h: float = 1.60,
        d0: float = 35.0,
    ):
        self.h = height
        self.w = width
        self.gamma_l = gamma_l
        self.gamma_h = gamma_h
        self.d0 = d0
        self._filter_grid: np.ndarray | None = None
        self._grid_shape: tuple[int, int] | None = None
        self._build_filter_grid(height, width)

    def _build_filter_grid(self, h: int, w: int) -> None:
        """Precomputes frequency response grid H(u, v) shifted for DFT direct multiplication."""
        crow, ccol = h // 2, w // 2
        u = np.arange(h) - crow
        v = np.arange(w) - ccol
        V, U = np.meshgrid(v, u)
        D2 = U**2 + V**2
        # Modified Gaussian High-Frequency Emphasis transfer function
        H = self.gamma_l + self.gamma_h * (1.0 - np.exp(-D2 / (2.0 * (self.d0**2))))
        # Shift zero-frequency to corners to match cv2.dft quadrant layout
        H_shifted = np.fft.ifftshift(H).astype(np.float32)
        # 2-channel representation for complex multiplication (Re, Im)
        self._filter_grid = np.repeat(H_shifted[:, :, np.newaxis], 2, axis=2)
        self._grid_shape = (h, w)

    def process_channel(self, channel: np.ndarray) -> np.ndarray:
        """Enhances a single 2D single-channel 8-bit image array in the Fourier domain."""
        h, w = channel.shape[:2]
        if self._grid_shape != (h, w):
            self._build_filter_grid(h, w)

        # Logarithmic domain transform: ln(1 + I) via SIMD C++ cv2.log
        float_ch = channel.astype(np.float32) + 1.0
        log_img = np.empty_like(float_ch)
        cv2.log(float_ch, log_img)

        # Forward 2D Discrete Fourier Transform
        dft = cv2.dft(log_img, flags=cv2.DFT_COMPLEX_OUTPUT)

        # In-place frequency domain multiplication: Z_filtered(u, v) = Z(u, v) * H(u, v)
        cv2.multiply(dft, self._filter_grid, dft)

        # Inverse 2D Discrete Fourier Transform
        idft = cv2.idft(dft, flags=cv2.DFT_SCALE | cv2.DFT_REAL_OUTPUT)

        # Exponentiation domain inversion via SIMD C++ cv2.exp
        exp_img = np.empty_like(idft)
        cv2.exp(idft, exp_img)

        # Fast C++ min-max scaling to 0..255
        return cv2.normalize(exp_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)


_FILTER_CACHE: dict[tuple[int, int, float, float, float], FourierHomomorphicFilter] = {}


def get_fourier_filter(h: int, w: int, gamma_l: float, gamma_h: float, d0: float) -> FourierHomomorphicFilter:
    key = (h, w, gamma_l, gamma_h, d0)
    if key not in _FILTER_CACHE:
        _FILTER_CACHE[key] = FourierHomomorphicFilter(h, w, gamma_l, gamma_h, d0)
    return _FILTER_CACHE[key]


def fourier_enhance_frame(
    frame: np.ndarray,
    gamma_l: float = 0.75,
    gamma_h: float = 1.60,
    d0: float = 35.0,
) -> np.ndarray:
    """Fourier high-frequency emphasis on LAB Lightness channel.
    
    Preserves exact chromatic color fidelity (A & B channels) while mathematically
    enhancing fine boundary harmonics and suppressing lighting unevenness.
    """
    if frame is None or frame.ndim != 3:
        return frame

    try:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        filt = get_fourier_filter(
            frame.shape[0],
            frame.shape[1],
            gamma_l=gamma_l,
            gamma_h=gamma_h,
            d0=d0,
        )
        l_enhanced = filt.process_channel(l_channel)

        merged = cv2.merge((l_enhanced, a_channel, b_channel))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    except Exception:
        return frame


class FourierSpectralSaliency:
    """Hou & Zhang (CVPR 2007) Spectral Residual visual saliency in Fourier domain."""

    @staticmethod
    def compute(frame: np.ndarray) -> np.ndarray:
        try:
            gray = (
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if frame.ndim == 3
                else frame.copy()
            )
            h, w = gray.shape[:2]
            # Use fixed resolution for fast spectral saliency
            small_h, small_w = 64, 64
            small = cv2.resize(gray, (small_w, small_h)).astype(np.float32)

            f = np.fft.fft2(small)
            mag = np.abs(f)
            phase = np.angle(f)
            log_mag = np.log(mag + 1e-6)

            # Spectral residual: subtract 3x3 local average with replicated boundaries
            kernel = np.ones((3, 3), dtype=np.float32) / 9.0
            spectral_residual = log_mag - cv2.filter2D(log_mag, -1, kernel, borderType=cv2.BORDER_REPLICATE)

            # Inverse transform with spectral residual magnitude and phase
            reconstruct = np.exp(spectral_residual + 1j * phase)
            saliency = np.abs(np.fft.ifft2(reconstruct)) ** 2
            saliency = cv2.GaussianBlur(saliency, (9, 9), 2.5)

            norm = cv2.normalize(saliency, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            return cv2.resize(norm, (w, h))
        except Exception:
            return np.zeros(frame.shape[:2], dtype=np.uint8)


class EllipticFourierDescriptor:
    """Calculates Elliptic Fourier Descriptors (EFD) for closed object contour shape verification."""

    @staticmethod
    def compute_descriptors(contour: np.ndarray, num_harmonics: int = 10) -> np.ndarray:
        """Computes scale-, translation-, and rotation-normalized harmonic coefficients."""
        try:
            pts = contour.reshape(-1, 2).astype(np.float32)
            k = len(pts)
            if k < 4:
                return np.zeros(num_harmonics, dtype=np.float32)

            # Displacement vectors along contour steps
            dxy = np.diff(pts, axis=0, append=pts[:1])
            dt = np.sqrt(dxy[:, 0] ** 2 + dxy[:, 1] ** 2)
            dt[dt == 0] = 1e-5
            t = np.concatenate(([0], np.cumsum(dt)))
            total_t = t[-1]
            if total_t <= 0:
                return np.zeros(num_harmonics, dtype=np.float32)

            harmonics = []
            for n in range(1, num_harmonics + 1):
                omega = 2.0 * np.pi * n / total_t
                an = np.sum(dxy[:, 0] / dt * (np.cos(omega * t[1:]) - np.cos(omega * t[:-1]))) / (omega**2)
                bn = np.sum(dxy[:, 0] / dt * (np.sin(omega * t[1:]) - np.sin(omega * t[:-1]))) / (omega**2)
                cn = np.sum(dxy[:, 1] / dt * (np.cos(omega * t[1:]) - np.cos(omega * t[:-1]))) / (omega**2)
                dn = np.sum(dxy[:, 1] / dt * (np.sin(omega * t[1:]) - np.sin(omega * t[:-1]))) / (omega**2)
                power = np.sqrt(an**2 + bn**2 + cn**2 + dn**2)
                harmonics.append(power)

            harmonics = np.array(harmonics, dtype=np.float32)
            # Scale normalization by fundamental harmonic
            if harmonics[0] > 1e-6:
                harmonics = harmonics / harmonics[0]
            return harmonics
        except Exception:
            return np.zeros(num_harmonics, dtype=np.float32)
