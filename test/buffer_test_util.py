from time import time, sleep
from tqdm.notebook import tqdm  
import numpy as np

class AcquisitionMonitor:
    def __init__(self, total_images=None, duration=None, buffer_capacity=None):
        """Initialize progress monitoring for acquisition
        
        Args:
            total_images: Number of images for sequence acquisition
            duration: Duration for continuous acquisition
            buffer_capacity: Total buffer capacity
        """
        self.pbar = None
        self.buffer_bar = None
        
        if duration is not None:
            self.pbar = tqdm(total=duration, desc='Continuous acquisition', 
                           position=0, leave=True)
        elif total_images is not None:
            self.pbar = tqdm(total=total_images, desc='Reading images',
                           position=0, leave=True)
            
        if buffer_capacity is not None:
            self.buffer_bar = tqdm(total=buffer_capacity, desc='Buffer free',
                                 position=1, leave=True)
    
    def update(self, images_read=None, elapsed_time=None, buffer_free=None):
        """Update progress bars"""
        if self.pbar is not None:
            if images_read is not None:
                self.pbar.n = images_read
            if elapsed_time is not None:
                self.pbar.n = elapsed_time
            self.pbar.refresh()
            
        if self.buffer_bar is not None and buffer_free is not None:
            self.buffer_bar.n = buffer_free
            self.buffer_bar.refresh()
    
    def close(self):
        """Close progress bars"""
        if self.pbar is not None:
            self.pbar.close()
        if self.buffer_bar is not None:
            self.buffer_bar.close()

def setup_camera(core, image_size, exposure=0.000001, fast_image=True):
    """Configure camera settings for speed tests"""
    core.set_property('Camera', 'OnCameraCCDYSize', str(image_size))
    core.set_property('Camera', 'OnCameraCCDXSize', str(image_size))
    if fast_image:
        core.set_property('Camera', 'FastImage', '1')
        core.snap_image()
    core.set_exposure(exposure)
    return core.get_image_buffer_size() / 1024 / 1024  # Returns MB per image

def run_live_mode(
    core,
    image_size: int = 1024,
    use_v2: bool = True,
    buffer_size_mb: float = 1000,
    duration: float = 5.0,
    check_for_changing_images: bool = False,
):
    """Run camera in continuous/live mode and monitor performance
    
    Args:
        core: MMCore instance
        duration: How long to run live mode in seconds
        read_images: Whether to read and verify images
    """

    core.enable_v2_buffer(use_v2)
    core.set_circular_buffer_memory_footprint(buffer_size_mb)

    try:
        core.stop_sequence_acquisition()
        core.start_continuous_sequence_acquisition(0)
        start_time = time()
        images = []
        last_image = None
        
        monitor = AcquisitionMonitor(duration=duration, buffer_capacity=core.get_buffer_total_capacity())
        
        while time() - start_time < duration:
            if check_for_changing_images:
                try:
                    live_image = core.get_last_tagged_image()
                except:
                    live_image = None
                
                if live_image is not None:
                    if last_image is None or not np.array_equal(live_image.pix, last_image.pix):
                        images.append(live_image)
                        last_image = live_image
                        if len(images) > 5:
                            images.pop(0)
                
            # Update progress
            monitor.update(
                elapsed_time=time() - start_time,
                buffer_free=core.get_buffer_free_capacity()
            )
            sleep(0.01)
        
        monitor.close()
        
        # Verify acquisition worked
        if check_for_changing_images:
            if len(images) == 0:
                raise Exception('No images captured in continuous mode')
            else:
                pixel_arrays = [img.pix for img in images]
                all_equal = all(np.array_equal(pixel_arrays[0], arr) for arr in pixel_arrays[1:])
                if all_equal:
                    raise Exception('All captured images were identical')
    
    except Exception as e:
        raise e
    finally:
        core.stop_sequence_acquisition()

def run_speed_test(
    core,
    image_size: int = 1024,
    n_images: int = 100,
    buffer_size_mb: float = 1000,
    n_trials: int = 1,
    use_v2: bool = True,
    exposure: float = 0.000001,
    read_images: bool = False,
):
    """Run speed test for sequence acquisition"""
    try:            
        results = {
            'params': {
                'image_size': image_size,
                'n_images': n_images,
                'buffer_size_mb': buffer_size_mb,
                'n_trials': n_trials,
                'use_v2': use_v2,
                'exposure': exposure,
                'read_images': read_images,
            },
            'data_rates': [],
            'setup_times': [],
            'frame_rates': []
        }
        MB_per_image = image_size**2 * 2 / 1024 / 1024

        core.enable_v2_buffer(use_v2)
        iterator = tqdm(range(n_trials), desc=f'Trial') if n_trials > 1 else range(n_trials)
        for trial in iterator:
            setup_time_start = time()
            core.set_buffer_memory_footprint(buffer_size_mb)
            core.reset_buffer()
            setup_time_end = time()

            start_time = time()
            core.start_sequence_acquisition(n_images, 0, True)

            if read_images:
                images_read = 0
                monitor = AcquisitionMonitor(
                    total_images=n_images,
                    buffer_capacity=core.get_buffer_total_capacity()
                )
                
                while images_read < n_images:
                    try:
                        im = core.pop_next_tagged_image()
                        if im is not None:
                            images_read += 1
                            monitor.update(
                                images_read=images_read,
                                buffer_free=core.get_buffer_free_capacity()
                            )
                    except:
                        sleep(0.001)
                    
                    if core.is_buffer_overflowed():
                        print('\nOverflow!')
                        break
                
                monitor.close()
            else:
                while core.is_sequence_running():
                    sleep(0.001)

            elapsed_time = time() - start_time

            if not core.is_buffer_overflowed():
                frame_rate = n_images/elapsed_time
                data_rate = frame_rate * MB_per_image / 1024
                results['data_rates'].append(data_rate)
                results['setup_times'].append(setup_time_end - setup_time_start)
                results['frame_rates'].append(frame_rate)
            else:
                print('Trial discarded due to overflow')

    except Exception as e:
        raise e
    finally:
        core.stop_sequence_acquisition()
    return results

def print_speed_results(results: dict):
    """Print formatted results from a speed test"""
    params = results['params']
    print("\n=== PERFORMANCE SUMMARY ===")
    print(f"{params['image_size']}x{params['image_size']} image; "
          f"{params['n_images']} images; {params['buffer_size_mb']} MB buffer; "
          f"{params['n_trials']} trials")
    print(f"Buffer v2={params['use_v2']}")
    
    if results['data_rates']:
        data_rates_array = np.array(results['data_rates'])
        mean_rate = np.mean(data_rates_array)
        std_rate = np.std(data_rates_array)
        ci_rate = np.percentile(data_rates_array, [2.5, 97.5])

        print(f"  Mean ± SD: {mean_rate:.3f} ± {std_rate:.3f} GB/s\n")
        print(f"  95% CI: [{ci_rate[0]:.3f}, {ci_rate[1]:.3f}] GB/s")
        print(f"  Individual trials: {', '.join(f'{r:.3f}' for r in data_rates_array)}")

        print(f"  Setup time: {np.mean(results['setup_times']):.3f} ± {np.std(results['setup_times']):.3f} s")
    else:
        print("No successful trials (all overflowed)")