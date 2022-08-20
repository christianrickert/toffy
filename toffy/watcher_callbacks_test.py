import os
import tempfile
from unittest.mock import patch
from pytest_cases import parametrize_with_cases

from mibi_bin_tools import io_utils

from toffy import watcher_callbacks
from toffy.test_utils import (
    mock_visualize_qc_metrics,
    ExtractionQCGenerationCases,
    ExtractionQCCallCases,
    PlotQCMetricsCases,
    check_extraction_dir_structure,
    check_qc_dir_structure,
    check_mph_dir_structure,
    check_stitched_dir_structure
)


@parametrize_with_cases('callbacks, kwargs', cases=ExtractionQCGenerationCases)
@parametrize_with_cases('data_path',  cases=ExtractionQCCallCases)
def test_build_fov_callback(callbacks, kwargs, data_path):

    intensities = kwargs.get('intensities', ['Au', 'chan_39'])
    replace = kwargs.get('replace', True)

    with tempfile.TemporaryDirectory() as tmp_dir:

        extracted_dir = os.path.join(tmp_dir, 'extracted')
        qc_dir = os.path.join(tmp_dir, 'qc')
        plot_dir = os.path.join(tmp_dir, 'plots')
        kwargs['tiff_out_dir'] = extracted_dir
        kwargs['qc_out_dir'] = qc_dir
        kwargs['mph_out_dir'] = qc_dir
        kwargs['plot_dir'] = plot_dir

        # test cb generates w/o errors
        cb = watcher_callbacks.build_fov_callback(*callbacks, **kwargs)

        point_names = io_utils.list_files(data_path, substrs=['bin'])
        point_names = [name.split('.')[0] for name in point_names]

        for name in point_names:
            cb(data_path, name)

        # just check SMA
        if 'extract_tiffs' in callbacks:
            check_extraction_dir_structure(extracted_dir, point_names, ['SMA'],
                                           intensities, replace)
        if 'generate_qc' in callbacks:
            check_qc_dir_structure(qc_dir, point_names)
        if 'generate_mph' in callbacks:
            check_mph_dir_structure(qc_dir, plot_dir, point_names)


@patch('toffy.watcher_callbacks.visualize_qc_metrics', side_effect=mock_visualize_qc_metrics)
@parametrize_with_cases('callbacks, kwargs', cases=PlotQCMetricsCases)
@parametrize_with_cases('data_path', cases=ExtractionQCCallCases)
def test_build_callbacks(viz_mock, callbacks, kwargs, data_path):
    with tempfile.TemporaryDirectory() as tmp_dir:

        extracted_dir = os.path.join(tmp_dir, 'extracted')
        stitched_dir = os.path.join(extracted_dir, 'stitched_images')
        qc_dir = os.path.join(tmp_dir, 'qc')
        plot_dir = os.path.join(tmp_dir, 'plots')
        kwargs['tiff_out_dir'] = extracted_dir
        kwargs['qc_out_dir'] = qc_dir
        kwargs['mph_out_dir'] = qc_dir
        kwargs['plot_dir'] = plot_dir

        if kwargs.get('save_dir', False):
            kwargs['save_dir'] = qc_dir

        fcb, rcb = watcher_callbacks.build_callbacks(run_callbacks=callbacks, **kwargs)

        point_names = io_utils.list_files(data_path, substrs=['bin'])
        point_names = [name.split('.')[0] for name in point_names]

        for name in point_names:
            fcb(data_path, name)
        rcb(data_path)

        check_extraction_dir_structure(extracted_dir, point_names, ['SMA'])
        check_qc_dir_structure(qc_dir, point_names, 'save_dir' in kwargs)
        check_mph_dir_structure(qc_dir, plot_dir, point_names, combined=True)
        check_stitched_dir_structure(stitched_dir, ['SMA'])
