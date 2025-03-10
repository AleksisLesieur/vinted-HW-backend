import sys
import time
import os
import signal
import multiprocessing as mp
import threading
from datetime import datetime
from collections import defaultdict

terminate_flag = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

def signal_handler(sig, frame):
    global terminate_flag
    print("\n\nCtrl+C detected. Shutting down...")
    terminate_flag = True
    time.sleep(0.5)

signal.signal(signal.SIGINT, signal_handler)


class RunStats:
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        
    def start(self):
        self.start_time = datetime.now()
        
    def end(self):
        self.end_time = datetime.now()
        
    def get_elapsed_time(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def format_elapsed_time(self):
        seconds = self.get_elapsed_time()
        
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
        elif minutes > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
        else:
            return f"{seconds} second{'s' if seconds != 1 else ''}"


class SimpleProgressBar:
    def __init__(self, total, prefix='Progress:', length=30):
        self.total = total
        self.prefix = prefix
        self.length = length
        self.start_time = time.time()
        self.last_update = 0
        self.iteration = 0
        
        self.GREEN = '\033[32m'
        self.YELLOW = '\033[33m'
        self.RED = '\033[31m'
        self.BLUE = '\033[34m'
        self.END = '\033[0m'
        self.BOLD = '\033[1m'
        
    def update(self, iteration):
        self.iteration = iteration
        current_time = time.time()
        if current_time - self.last_update < 0.1 and iteration < self.total:
            return
        
        self.last_update = current_time
        percentage = min(100, 100 * (iteration / float(self.total)))
        filled_length = int(self.length * iteration // self.total)
        
        empty = '░'
        full = '█'

        bar = self.BOLD + full * filled_length + self.END + empty * (self.length - filled_length)

        elapsed = current_time - self.start_time
        if iteration > 0:
            items_per_second = iteration / elapsed
            eta = (self.total - iteration) / items_per_second if items_per_second > 0 else 0
            
            if eta > 3600:
                time_str = f"{eta//3600:.0f}h {(eta%3600)//60:.0f}m {eta%60:.0f}s"
            elif eta > 60:
                time_str = f"{eta//60:.0f}m {eta%60:.0f}s"
            else:
                time_str = f"{eta:.0f}s"
                
            eta_str = f"ETA: {time_str}"
        else:
            items_per_second = 0
            eta_str = "ETA: --"

        progress_bar = f"\r{self.BOLD}{self.prefix}{self.END} |{bar}| {percentage:.1f}% ({iteration:,}/{self.total:,}) {items_per_second:.1f} lines/s {eta_str}"
        
        print(progress_bar, end='', flush=True)

        if iteration >= self.total:
            print("")
            print(f"{self.BOLD}Finalizing process... Please wait{self.END}")


class ShippingCalculator:
    def __init__(self):
        self.prices = {
            'LP': {'S': 1.50, 'M': 4.90, 'L': 6.90},
            'MR': {'S': 2.00, 'M': 3.00, 'L': 4.00}
        }
        self.lowest_s_price = min(self.prices[p]['S'] for p in self.prices)
        self.valid_providers = set(self.prices.keys())
        self.valid_sizes = {'S', 'M', 'L'}
        self.monthly_discounts = defaultdict(float)
        self.monthly_lp_l_count = defaultdict(int)

        self.lines_processed = 0
        self.valid_lines = 0
        self.ignored_lines = 0
        self.total_discount_applied = 0.0

        self.provider_counts = defaultdict(int)
        self.size_counts = defaultdict(int)

        self.lock = mp.Lock() if mp.current_process().name != 'MainProcess' else None
    
    def get_month_key(self, date):
        return date.strftime("%Y-%m")
    
    def calculate_discount(self, date, size, provider):
        if provider not in self.valid_providers or size not in self.valid_sizes:
            return None

        self.provider_counts[provider] += 1
        self.size_counts[size] += 1
        
        base_price = self.prices[provider][size]
        discount = 0.0
        month_key = self.get_month_key(date)

        if size == 'S' and base_price > self.lowest_s_price:
            discount += base_price - self.lowest_s_price

        if provider == 'LP' and size == 'L':
            if self.lock:
                with self.lock:
                    self.monthly_lp_l_count[month_key] += 1
                    if self.monthly_lp_l_count[month_key] == 3:
                        discount += base_price
            else:
                self.monthly_lp_l_count[month_key] += 1
                if self.monthly_lp_l_count[month_key] == 3:
                    discount += base_price

        if self.lock:
            with self.lock:
                available_discount = 10.0 - self.monthly_discounts[month_key]
                applicable_discount = min(discount, available_discount)
                self.monthly_discounts[month_key] += applicable_discount
                self.total_discount_applied += applicable_discount
        else:
            available_discount = 10.0 - self.monthly_discounts[month_key]
            applicable_discount = min(discount, available_discount)
            self.monthly_discounts[month_key] += applicable_discount
            self.total_discount_applied += applicable_discount

        final_price = base_price - applicable_discount
        
        return base_price, applicable_discount, final_price
    
    def process_transaction(self, line):
        self.lines_processed += 1

        line = line.strip()
        if not line:
            self.ignored_lines += 1
            return ""
        
        parts = line.split()

        if len(parts) != 3:
            self.ignored_lines += 1
            return f"{line} Ignored"
        
        date_str, size, provider = parts
        
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self.ignored_lines += 1
            return f"{line} Ignored"
        
        result = self.calculate_discount(date, size, provider)
        
        if result is None:
            self.ignored_lines += 1
            return f"{line} Ignored"
        
        self.valid_lines += 1
        base_price, discount, final_price = result

        if discount > 0:
            return f"{line} {final_price:.2f} {discount:.2f}"
        else:
            return f"{line} {final_price:.2f} -"

    def print_statistics(self, run_stats):
        elapsed_time_str = run_stats.format_elapsed_time()

        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        RED = '\033[31m'
        BLUE = '\033[34m'
        CYAN = '\033[36m'
        MAGENTA = '\033[35m'
        BOLD = '\033[1m'
        END = '\033[0m'
        
        BOX_TL = '┌'
        BOX_TR = '┐'
        BOX_BL = '└'
        BOX_BR = '┘'
        BOX_H = '─'
        BOX_V = '│'

        terminal_width = min(80, self._get_terminal_width())
        box_width = terminal_width - 2

        print(f"\n{CYAN}{BOX_TL}{BOX_H * box_width}{BOX_TR}{END}")
        
        title = "Processing Summary"
        padding = (box_width - len(title)) // 2
        print(f"{CYAN}{BOX_V}{END}{' ' * padding}{BOLD}{MAGENTA}{title}{END}{' ' * (box_width - padding - len(title))}{CYAN}{BOX_V}{END}")
        
        print(f"{CYAN}{BOX_V}{END}{CYAN}{BOX_H * box_width}{END}{CYAN}{BOX_V}{END}")

        start_time = run_stats.start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_time = run_stats.end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        self._print_stat_line(BOX_V, "Start time:", start_time, box_width, CYAN, BLUE, END)
        self._print_stat_line(BOX_V, "End time:", end_time, box_width, CYAN, BLUE, END)
        self._print_stat_line(BOX_V, "Duration:", elapsed_time_str, box_width, CYAN, GREEN, END)
        self._print_stat_line(BOX_V, "Lines processed:", f"{self.lines_processed:,}", box_width, CYAN, YELLOW, END)
        self._print_stat_line(BOX_V, "Valid transactions:", f"{self.valid_lines:,}", box_width, CYAN, GREEN, END)
        self._print_stat_line(BOX_V, "Ignored lines:", f"{self.ignored_lines:,}", box_width, CYAN, RED, END)
        self._print_stat_line(BOX_V, "Total discount:", f"€{self.total_discount_applied:.2f}", box_width, CYAN, GREEN, END)

        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            self._print_stat_line(BOX_V, "Memory usage:", f"{memory_mb:.2f} MB", box_width, CYAN, BLUE, END)

        print(f"{CYAN}{BOX_V}{END}{' ' * box_width}{CYAN}{BOX_V}{END}")
        self._print_stat_line(BOX_V, "Provider statistics:", "", box_width, CYAN, MAGENTA, END)
        
        for provider, count in sorted(self.provider_counts.items()):
            self._print_stat_line(BOX_V, f"   {provider}:", f"{count:,} shipments", box_width, CYAN, BLUE, END)
        
        print(f"{CYAN}{BOX_V}{END}{' ' * box_width}{CYAN}{BOX_V}{END}")
        self._print_stat_line(BOX_V, "Package size statistics:", "", box_width, CYAN, MAGENTA, END)
        
        for size, count in sorted(self.size_counts.items()):
            self._print_stat_line(BOX_V, f"   {size}:", f"{count:,} shipments", box_width, CYAN, BLUE, END)
        
        print(f"{CYAN}{BOX_BL}{BOX_H * box_width}{BOX_BR}{END}")
    
    def _print_stat_line(self, box_char, label, value, width, box_color, value_color, end_color):
        print(f"{box_color}{box_char}{end_color} {label} {value_color}{value}{end_color}{' ' * (width - len(label) - len(value) - 3)}{box_color}{box_char}{end_color}")
        
    def _get_terminal_width(self):
        try:
            return os.get_terminal_size().columns
        except (AttributeError, OSError):
            return 80


def count_lines_in_file(file_path):

    try:
        with open(file_path, 'r') as f:
            line_count = sum(1 for _ in f)
        return line_count
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error counting lines: {str(e)}")
        return 0


def read_chunk_from_file(file_path, start_line, end_line):
    chunk = []
    with open(file_path, 'r') as f:
        for _ in range(start_line):
            next(f)

        for _ in range(end_line - start_line):
            try:
                line = next(f)
                chunk.append(line)
            except StopIteration:
                break
                
    return chunk


def process_chunk(args):
    global terminate_flag
    file_path, start_line, end_line, worker_id, progress_dict, progress_dict_lock = args

    calculator = ShippingCalculator()
    chunk = read_chunk_from_file(file_path, start_line, end_line)
    results = []
    lines_processed = 0
    
    for line in chunk:
        if terminate_flag:
            break
            
        result = calculator.process_transaction(line)
        if result:
            results.append(result)
        
        lines_processed += 1

        if lines_processed % 1000 == 0 or lines_processed == len(chunk):
            with progress_dict_lock:
                progress_dict[worker_id] = lines_processed
    
    with progress_dict_lock:
        progress_dict[worker_id] = lines_processed
    
    return {
        'results': results,
        'lines_processed': calculator.lines_processed,
        'valid_lines': calculator.valid_lines,
        'ignored_lines': calculator.ignored_lines,
        'total_discount_applied': calculator.total_discount_applied,
        'monthly_lp_l_count': dict(calculator.monthly_lp_l_count),
        'monthly_discounts': dict(calculator.monthly_discounts),
        'provider_counts': dict(calculator.provider_counts),
        'size_counts': dict(calculator.size_counts),
        'chunk_size': len(chunk),
        'start_line': start_line,
        'end_line': end_line
    }


def process_file_parallel(input_file, output_file=None, num_processes=None):
    global terminate_flag
    run_stats = RunStats()
    run_stats.start()
    
    if num_processes is None:
        num_processes = min(4, mp.cpu_count())

    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    BOLD = '\033[1m'
    END = '\033[0m'
    
    print(f"\n{BOLD}{CYAN}Analyzing file:{END} {YELLOW}{input_file}{END}")
    print(f"{BOLD}{BLUE}Using {num_processes} parallel processes{END}")
    
    print(f"{BOLD}{MAGENTA}Counting lines in file...{END}")
    total_lines = count_lines_in_file(input_file)
    print(f"{BOLD}{GREEN}Found {total_lines:,} lines to process{END}")
    
    progress = SimpleProgressBar(total_lines, prefix='Processing')
    
    print(f"{BOLD}{MAGENTA}Dividing file into chunks...{END}")
    chunk_size = total_lines // num_processes
    remainder = total_lines % num_processes

    chunk_boundaries = []
    start_line = 0
    
    for i in range(num_processes):
        this_chunk_size = chunk_size + (1 if i < remainder else 0)
        end_line = start_line + this_chunk_size
        chunk_boundaries.append((start_line, end_line))
        start_line = end_line
    
    GREEN = '\033[32m'
    BOLD = '\033[1m'
    END = '\033[0m'
    print(f"{BOLD}{GREEN}Created {num_processes} chunks of approximately {chunk_size:,} lines each{END}")
    
    manager = mp.Manager()
    progress_dict = manager.dict()
    progress_dict_lock = manager.Lock()
    
    for i in range(num_processes):
        progress_dict[i] = 0
        
    all_results = []
    calculator = ShippingCalculator()
    args = [(input_file, chunk_boundaries[i][0], chunk_boundaries[i][1], i, progress_dict, progress_dict_lock) 
            for i in range(num_processes)]
    
    def update_progress_thread():
        global terminate_flag
        total_processed = 0
        while total_processed < total_lines and not terminate_flag:
            with progress_dict_lock:
                total_processed = sum(progress_dict.values())

            progress.update(min(total_processed, total_lines))
            
            if total_processed >= total_lines * 0.99:
                break

            time.sleep(0.1)
    
    update_thread = threading.Thread(target=update_progress_thread)
    update_thread.daemon = True
    update_thread.start()

    pool = None
    results = []
    
    try:
        pool = mp.Pool(processes=num_processes)
        result_iter = pool.imap_unordered(process_chunk, args)
        
        while True:
            try:
                if terminate_flag:
                    if pool:
                        pool.terminate()
                        pool.join()
                    print("\nProcess terminated by user.")
                    return None

                result = next(result_iter)
                
                if output_file is None:
                    all_results.extend(result['results'][:1000] if len(all_results) < 1000 else [])

                calculator.lines_processed += result['lines_processed']
                calculator.valid_lines += result['valid_lines']
                calculator.ignored_lines += result['ignored_lines']
                calculator.total_discount_applied += result['total_discount_applied']

                for month, count in result['monthly_lp_l_count'].items():
                    calculator.monthly_lp_l_count[month] += count
                
                for month, discount in result['monthly_discounts'].items():
                    calculator.monthly_discounts[month] += discount
                
                for provider, count in result['provider_counts'].items():
                    calculator.provider_counts[provider] += count
                    
                for size, count in result['size_counts'].items():
                    calculator.size_counts[size] += count
          
                results.append(result['results'])
                
            except StopIteration:
                break
            except Exception as e:
                if not terminate_flag:
                    print(f"Error processing results: {str(e)}")
                break

        if pool:
            pool.close()
            pool.join()
            
        if terminate_flag:
            return None

        progress.update(total_lines)

        if output_file:
            with open(output_file, 'w') as f:
                for chunk_results in results:
                    for result in chunk_results:
                        f.write(result + '\n')

        run_stats.end()
        calculator.print_statistics(run_stats)
        
        print()

        if output_file is None:
            return all_results
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        if pool:
            pool.terminate()
            pool.join()
        return None
        
    except Exception as e:
        if not terminate_flag:
            print(f"Error processing file: {str(e)}")
            import traceback
            print(traceback.format_exc())
        if pool:
            pool.terminate()
            pool.join()
        return None


def main():
    global terminate_flag
    
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    BOLD = '\033[1m'
    END = '\033[0m'
    
    BOX_TL = '┌'
    BOX_TR = '┐'
    BOX_BL = '└'
    BOX_BR = '┘'
    BOX_H = '─'
    BOX_V = '│'
    
    terminal_width = min(80, os.get_terminal_size().columns)
    box_width = terminal_width - 2
    
    print(f"\n{CYAN}{BOX_TL}{BOX_H * box_width}{BOX_TR}{END}")
    
    title = "Vinted Shipping Discount Calculator"
    padding = (box_width - len(title)) // 2
    print(f"{CYAN}{BOX_V}{END}{' ' * padding}{BOLD}{MAGENTA}{title}{END}{' ' * (box_width - padding - len(title))}{CYAN}{BOX_V}{END}")
    
    print(f"{CYAN}{BOX_BL}{BOX_H * box_width}{BOX_BR}{END}")
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "input.txt"
    
    if len(sys.argv) > 2:
        if sys.argv[2].lower() == "--quiet" or sys.argv[2].lower() == "-q":
            output_file = None
        else:
            output_file = sys.argv[2]
    else:
        output_file = None
    
    num_processes = None
    for i, arg in enumerate(sys.argv):
        if arg == "--processes" or arg == "-p":
            if i + 1 < len(sys.argv):
                try:
                    num_processes = int(sys.argv[i + 1])
                except ValueError:
                    pass
    
    if output_file:
        open(output_file, 'w').close()
        CYAN = '\033[36m'
        BOLD = '\033[1m'
        END = '\033[0m'
        print(f"{BOLD}{CYAN}Output will be saved to: {output_file}{END}")
    
    try:
        results = process_file_parallel(input_file, output_file, num_processes)

        if terminate_flag or results is None:
            print("Processing terminated. Exiting...")
            sys.exit(0)

        if not output_file and results:
            display_results_summary(results, input_file)
    
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(0)


def display_results_summary(results, input_file):

    CYAN = '\033[36m'
    YELLOW = '\033[33m'
    BOLD = '\033[1m'
    END = '\033[0m'
    
    BOX_TL = '┌'
    BOX_TR = '┐'
    BOX_BL = '└'
    BOX_BR = '┘'
    BOX_H = '─'
    BOX_V = '│'
    
    terminal_width = min(80, os.get_terminal_size().columns)
    box_width = terminal_width - 2
    
    print(f"\n{CYAN}{BOX_TL}{BOX_H * box_width}{BOX_TR}{END}")
    
    title = "Results Summary"
    padding = (box_width - len(title)) // 2
    print(f"{CYAN}{BOX_V}{END}{' ' * padding}{BOLD}{YELLOW}{title}{END}{' ' * (box_width - padding - len(title))}{CYAN}{BOX_V}{END}")
    
    print(f"{CYAN}{BOX_V}{END}{CYAN}{BOX_H * box_width}{END}{CYAN}{BOX_V}{END}")
    
    if len(results) > 0:
        print(f"{CYAN}{BOX_V}{END} Sample of processed transactions:{' ' * (box_width - 30)}{CYAN}{BOX_V}{END}")
        
        for i, result in enumerate(results[:10]):
            padding = box_width - len(result) - 2
            if padding < 0:
                result = result[:box_width-5] + "..."
                padding = 0
            print(f"{CYAN}{BOX_V}{END} {result}{' ' * padding}{CYAN}{BOX_V}{END}")
        
        if len(results) > 10:
            more_msg = f"... and {len(results) - 10:,} more transactions"
            padding = box_width - len(more_msg) - 2
            print(f"{CYAN}{BOX_V}{END} {more_msg}{' ' * padding}{CYAN}{BOX_V}{END}")
    
    print(f"{CYAN}{BOX_V}{END}{' ' * box_width}{CYAN}{BOX_V}{END}")
    
    help_msg = "To see all results, use:"
    padding = box_width - len(help_msg) - 2
    print(f"{CYAN}{BOX_V}{END} {help_msg}{' ' * padding}{CYAN}{BOX_V}{END}")
    
    cmd_msg = f"python {sys.argv[0]} {input_file} output.txt"
    padding = box_width - len(cmd_msg) - 2
    print(f"{CYAN}{BOX_V}{END} {cmd_msg}{' ' * padding}{CYAN}{BOX_V}{END}")
    
    help_msg2 = "Then check the output.txt file"
    padding = box_width - len(help_msg2) - 2
    print(f"{CYAN}{BOX_V}{END} {help_msg2}{' ' * padding}{CYAN}{BOX_V}{END}")
    
    print(f"{CYAN}{BOX_BL}{BOX_H * box_width}{BOX_BR}{END}")


if __name__ == "__main__":
    terminate_flag = False
    main()