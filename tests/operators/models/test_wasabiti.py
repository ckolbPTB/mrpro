"""Tests for the WASABITI signal model."""

import pytest
import torch
from mrpro.operators.models import WASABITI
from tests import autodiff_test
from tests.operators.models.conftest import SHAPE_VARIATIONS_SIGNAL_MODELS, create_parameter_tensor_tuples


def create_data(
    offset_max=500, n_offsets=101, b0_shift=0, relative_b1=1.0, t1=1.0
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    offsets = torch.linspace(-offset_max, offset_max, n_offsets)
    return offsets, torch.Tensor([b0_shift]), torch.Tensor([relative_b1]), torch.Tensor([t1])


def test_WASABITI_symmetry():
    """Test symmetry property of complete WASABITI spectra."""
    offsets, b0_shift, relative_b1, t1 = create_data()
    wasabiti_model = WASABITI(offsets=offsets, recovery_time=torch.ones_like(offsets))
    (signal,) = wasabiti_model(b0_shift, relative_b1, t1)

    # check that all values are symmetric around the center
    assert torch.allclose(signal, signal.flipud(), rtol=1e-15), 'Result should be symmetric around center'


def test_WASABITI_symmetry_after_shift():
    """Test symmetry property of shifted WASABITI spectra."""
    offsets_shifted, b0_shift, relative_b1, t1 = create_data(b0_shift=100)
    recovery_time = torch.ones_like(offsets_shifted)
    wasabiti_model = WASABITI(offsets=offsets_shifted, recovery_time=recovery_time)
    (signal_shifted,) = wasabiti_model(b0_shift, relative_b1, t1)

    lower_index = int((offsets_shifted == -300).nonzero()[0][0])
    upper_index = int((offsets_shifted == 500).nonzero()[0][0])

    assert signal_shifted[lower_index] == signal_shifted[upper_index], 'Result should be symmetric around shift'


def test_WASABITI_asymmetry_for_non_unique_recovery_time():
    """Test symmetry property of WASABITI spectra for non-unique recovery_time values."""
    offsets_unshifted, b0_shift, relative_b1, t1 = create_data(n_offsets=11)
    recovery_time = torch.ones_like(offsets_unshifted)
    # set first half of recovery_time values to 2.0
    recovery_time[: len(offsets_unshifted) // 2] = 2.0

    wasabiti_model = WASABITI(offsets=offsets_unshifted, recovery_time=recovery_time)
    (signal,) = wasabiti_model(b0_shift, relative_b1, t1)

    assert not torch.allclose(signal, signal.flipud(), rtol=1e-8), 'Result should not be symmetric around center'


@pytest.mark.parametrize('t1', [(1), (2), (3)])
def test_WASABITI_relaxation_term(t1):
    """Test relaxation term (Mzi) of WASABITI model."""
    offsets, b0_shift, relative_b1, t1 = create_data(offset_max=50000, n_offsets=1, t1=t1)
    recovery_time = torch.ones_like(offsets) * t1
    wasabiti_model = WASABITI(offsets=offsets, recovery_time=recovery_time)
    sig = wasabiti_model(b0_shift, relative_b1, t1)

    assert torch.isclose(sig[0], torch.FloatTensor([1 - torch.exp(torch.FloatTensor([-1]))]), rtol=1e-8)


def test_WASABITI_offsets_recovery_time_mismatch():
    """Verify error for shape mismatch."""
    offsets = torch.ones((1, 2))
    recovery_time = torch.ones((1,))
    with pytest.raises(ValueError, match='Shape of recovery_time'):
        WASABITI(offsets=offsets, recovery_time=recovery_time)


@SHAPE_VARIATIONS_SIGNAL_MODELS
def test_WASABITI_shape(parameter_shape, contrast_dim_shape, signal_shape):
    """Test correct signal shapes."""
    offsets, recovery_time = create_parameter_tensor_tuples(contrast_dim_shape, number_of_tensors=2)
    model_op = WASABITI(offsets=offsets, recovery_time=recovery_time)
    b0_shift, relative_b1, t1 = create_parameter_tensor_tuples(parameter_shape, number_of_tensors=3)
    (signal,) = model_op(b0_shift, relative_b1, t1)
    assert signal.shape == signal_shape


def test_autodiff_WASABITI():
    """Test autodiff works for WASABITI model."""
    offsets, b0_shift, relative_b1, t1 = create_data(offset_max=300, n_offsets=2)
    recovery_time = torch.ones_like(offsets) * t1
    wasabiti_model = WASABITI(offsets=offsets, recovery_time=recovery_time)
    autodiff_test(wasabiti_model, b0_shift, relative_b1, t1)


@pytest.mark.cuda
def test_wasabiti_cuda():
    """Test the WASABITI model works on cuda devices."""
    offsets, b0_shift, relative_b1, t1 = create_data(offset_max=300, n_offsets=2)
    recovery_time = torch.ones_like(offsets) * t1

    # Create on CPU, transfer to GPU and run on GPU
    model = WASABITI(offsets=offsets, recovery_time=recovery_time)
    model.cuda()
    (signal,) = model(b0_shift.cuda(), relative_b1.cuda(), t1.cuda())
    assert signal.is_cuda

    # Create on GPU and run on GPU
    model = WASABITI(offsets=offsets.cuda(), recovery_time=recovery_time)
    (signal,) = model(b0_shift.cuda(), relative_b1.cuda(), t1.cuda())
    assert signal.is_cuda

    # Create on GPU, transfer to CPU and run on CPU
    model = WASABITI(offsets=offsets.cuda(), recovery_time=recovery_time)
    model.cpu()
    (signal,) = model(b0_shift, relative_b1, t1)
    assert signal.is_cpu
