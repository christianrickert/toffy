import os
import tempfile
import shutil
from unittest.mock import patch
from pytest_cases import parametrize_with_cases

from mibi_bin_tools import io_utils

from toffy import watcher_callbacks
from toffy.json_utils import write_json_file
from toffy.test_utils import (
    mock_visualize_qc_metrics,
    FovCallbackCases,
    WatcherTestData,
    RunCallbackCases,
    check_extraction_dir_structure,
    check_qc_dir_structure,
    check_mph_dir_structure,
    check_pulse_dir_structure,
    check_stitched_dir_structure,
)

COMBINED_RUN_JSON_SPOOF = {
    'fovs': [
        {'runOrder': 1, 'scanCount': 1, 'frameSizePixels': {'width': 32, 'height': 32}},
        {'runOrder': 2, 'scanCount': 1, 'frameSizePixels': {'width': 32, 'height': 32}},
    ],
}


@parametrize_with_cases('callbacks, kwargs', cases=FovCallbackCases)
@parametrize_with_cases('data_path',  cases=WatcherTestData)
def test_build_fov_callback(callbacks, kwargs, data_path):

    intensities = kwargs.get('intensities', ['Au', 'chan_39'])
    replace = kwargs.get('replace', True)

    with tempfile.TemporaryDirectory() as tmp_dir:

        extracted_dir = os.path.join(tmp_dir, 'extracted')
        file_dir = os.path.join(tmp_dir, 'fov_data')
        plot_dir = os.path.join(tmp_dir, 'plots')
        kwargs['tiff_out_dir'] = extracted_dir
        kwargs['qc_out_dir'] = file_dir
        kwargs['mph_out_dir'] = file_dir
        kwargs['pulse_out_dir'] = file_dir
        kwargs['plot_dir'] = plot_dir

        run_data = os.path.join(tmp_dir, 'tissue')
        os.makedirs(run_data)
        for fov in ['fov-1-scan-1.bin', 'fov-1-scan-1.json',
                    'fov-2-scan-1.bin', 'fov-2-scan-1.json']:
            shutil.copy(os.path.join(data_path, fov),
                        os.path.join(run_data, fov))

        write_json_file(json_path=os.path.join(run_data, 'tissue.json'),
                        json_object=COMBINED_RUN_JSON_SPOOF)

        # test cb generates w/o errors
        cb = watcher_callbacks.build_fov_callback(*callbacks, **kwargs)

        point_names = io_utils.list_files(run_data, substrs=['bin'])
        point_names = [name.split('.')[0] for name in point_names]

        for name in point_names:
            cb(run_data, name)

        # just check SMA
        if 'extract_tiffs' in callbacks:
            check_extraction_dir_structure(extracted_dir, point_names, [], ['SMA'],
                                           intensities, replace)
        if 'generate_qc' in callbacks:
            check_qc_dir_structure(file_dir, point_names, [])
        if 'generate_mph' in callbacks:
            check_mph_dir_structure(file_dir, plot_dir, point_names, [])
        if 'generate_pulse_heights' in callbacks:
            check_pulse_dir_structure(file_dir, point_names, [])


@patch('toffy.watcher_callbacks.visualize_qc_metrics', side_effect=mock_visualize_qc_metrics)
@parametrize_with_cases('callbacks, kwargs', cases=RunCallbackCases)
@parametrize_with_cases('data_path', cases=WatcherTestData)
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

        run_data = os.path.join(tmp_dir, 'tissue')
        os.makedirs(run_data)
        for fov in ['fov-1-scan-1.bin', 'fov-1-scan-1.json',
                    'fov-2-scan-1.bin', 'fov-2-scan-1.json']:
            shutil.copy(os.path.join(data_path, fov),
                        os.path.join(run_data, fov))

        write_json_file(json_path=os.path.join(run_data, 'tissue.json'),
                        json_object=COMBINED_RUN_JSON_SPOOF)

        point_names = io_utils.list_files(run_data, substrs=['bin'])
        point_names = [name.split('.')[0] for name in point_names]

        for name in point_names:
            fcb(run_data, name)
        rcb(run_data)

        check_extraction_dir_structure(extracted_dir, point_names, [], ['SMA'])
        check_qc_dir_structure(qc_dir, point_names, [], 'save_dir' in kwargs)
        check_mph_dir_structure(qc_dir, plot_dir, point_names, [], combined=True)
        check_stitched_dir_structure(stitched_dir, ['SMA'])
