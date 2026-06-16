"""
qs-kernel: Quantum Star kernel bootstrap runner.

Produces byte-stable canonical artifacts from runKernel(repo), or CI fails.
Public surface: run_kernel, KernelOutputs, load_config, KernelConfig.
"""
from .runner import run_kernel, KernelOutputs
from .config import load_config, KernelConfig

__version__ = "1.0.0"
__all__ = ["run_kernel", "KernelOutputs", "load_config", "KernelConfig", "__version__"]
