import sys
import os
import ftplib
import re
import numpy as np
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QDateEdit, QFileDialog, 
                             QMessageBox, QComboBox, QGroupBox, QCheckBox, QGridLayout)
from PyQt5.QtCore import QDate
from PyQt5.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import allantools as allan
from scipy.signal import kaiserord, lfilter, firwin, detrend

class SP3Processor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS SP3 Processor")
        self.setGeometry(100, 100, 500, 500)
        
        self.phaselim = 100

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create UI elements
        self.create_folder_selection(main_layout)
        self.create_date_selection(main_layout)
        self.create_satellite_selection(main_layout)
        self.create_settings(main_layout)
        self.create_plot_options(main_layout)
        self.create_processing_options(main_layout)
        self.create_action_buttons(main_layout)
        
        # Initialize variables
        self.sp3_folder = os.path.join(os.getcwd(), "sp3_files")
        self.folder_entry.setText(self.sp3_folder)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.end_date.setDate(QDate.currentDate())
        
        # Data storage
        self.data = {}
        
        # Set up plot window
        # self.plot_phase_detrended = None
        # self.plot_phase_dedrifted = None
        # self.plot_freq = None
        # self.plot_adev = None

        self.pltcnt = -1
        self.fpltcnt = -1
        self.adevcnt = -1
        self.psdcnt = -1
        self.plot_phase_detrended = []
        self.plot_phase_dedrifted = []
        self.plot_freq = []
        self.plot_adev = []
        self.plot_psd = []

        self.maxdate = QDate()
        self.mindate = QDate()        

    def create_folder_selection(self, layout):
        #group = QGroupBox("SP3 Files Folder")
        group = QGroupBox("Каталог с файлами SP3")
        group_layout = QVBoxLayout(group)
        
        folder_layout = QHBoxLayout()
        #folder_layout.addWidget(QLabel("Folder:"))
        folder_layout.addWidget(QLabel("Каталог:"))
        
        self.folder_entry = QLineEdit()
        folder_layout.addWidget(self.folder_entry)
        
        #browse_button = QPushButton("Browse...")
        browse_button = QPushButton("Выбрать...")
        browse_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_button)
        
        group_layout.addLayout(folder_layout)
        layout.addWidget(group)

    def create_date_selection(self, layout):
        #group = QGroupBox("Date Range")
        group = QGroupBox("Выбрать период для обработки")
        group_layout = QHBoxLayout(group)
        
        #group_layout.addWidget(QLabel("Start Date:"))
        group_layout.addWidget(QLabel("Дата начала:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        group_layout.addWidget(self.start_date)
        
        #group_layout.addWidget(QLabel("End Date:"))
        group_layout.addWidget(QLabel("Дата конца:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        group_layout.addWidget(self.end_date)
        
        layout.addWidget(group)

    def create_satellite_selection(self, layout):
        #group = QGroupBox("Satellites to Analyze")
        group = QGroupBox("Выбор спутников")
        group_layout = QVBoxLayout(group)
        
        self.sat_entry = QLineEdit()
        #self.sat_entry.setPlaceholderText("Enter satellite IDs (e.g., G01, G02, R03) separated by commas")
        self.sat_entry.setPlaceholderText("Идентификаторы спутников (например, G01, G02, R03) разделитель - запятая")
        group_layout.addWidget(self.sat_entry)              
        
        # Predefined satellites for quick selection
        preset_layout = QHBoxLayout()
        #preset_layout.addWidget(QLabel("Preset Satellites:"))
        preset_layout.addWidget(QLabel("Наборы спутников:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("ГЛОНАСС-K2 (R26-R27)", ["R{:02d}".format(i) for i in range(26, 28)])
        self.preset_combo.addItem("ГЛОНАСС (R01-R27)", ["R{:02d}".format(i) for i in range(1, 28)])
        self.preset_combo.addItem("GPS Block IIF (G01-G10)", ["G{:02d}".format(i) for i in range(1, 11)])
        self.preset_combo.addItem("GPS Block III (G11-G15)", ["G{:02d}".format(i) for i in range(11, 16)])        
        self.preset_combo.addItem("Galileo (E02-E22)", ["E{:02d}".format(i) for i in range(2, 22)])
        self.preset_combo.addItem("Beidou (C06-C45)", ["C{:02d}".format(i) for i in range(6, 45)])
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)
        self.apply_preset()
        preset_layout.addWidget(self.preset_combo)
        
        group_layout.addLayout(preset_layout)
        layout.addWidget(group)

    def create_settings(self, layout):
        #group = QGroupBox("Satellites to Analyze")
        group = QGroupBox("Параметры обработки")
        group_layout = QVBoxLayout(group)
        
        self.ref02_chk = QCheckBox("Использовать данные Новосибирска")
        self.ref02_chk.setChecked(True)
        group_layout.addWidget(self.ref02_chk)              
                
        glue_layout = QHBoxLayout()
        self.glue_chk = QCheckBox("Устранять разрывы более (пс):")
        self.glue_chk.setChecked(True)
        glue_layout.addWidget(self.glue_chk)
        self.phaselim_entry = QLineEdit()
        self.phaselim_entry.setText(str(self.phaselim))
        glue_layout.addWidget(self.phaselim_entry)
        group_layout.addLayout(glue_layout)

        layout.addWidget(group)
    
    def create_plot_options(self, layout):        
        #group = QGroupBox("Processing Options")
        group = QGroupBox("Выводить графики")
        group_layout = QHBoxLayout(group)
        
        self.phaseplot_chk = QCheckBox("Фаза")
        self.phaseplot_chk.setChecked(True)
        group_layout.addWidget(self.phaseplot_chk)

        self.freqplot_chk = QCheckBox("Частота")
        self.freqplot_chk.setChecked(True)
        group_layout.addWidget(self.freqplot_chk)

        self.adevplot_chk = QCheckBox("СКДО")
        self.adevplot_chk.setChecked(True)
        group_layout.addWidget(self.adevplot_chk)

        self.psdplot_chk = QCheckBox("Спектр")
        self.psdplot_chk.setChecked(True)
        group_layout.addWidget(self.psdplot_chk)

        layout.addWidget(group)

    def create_processing_options(self, layout):        
        #group = QGroupBox("Processing Options")
        group = QGroupBox("Параметры отображения СКДО")
        group_layout = QGridLayout(group)
        
        self.drift_chk = QCheckBox("Вычитать дрейф частоты при расчете СКДО")
        self.drift_chk.setChecked(True)
        group_layout.addWidget(self.drift_chk)

        self.dayline_chk = QCheckBox("Показать линию для интервала 1 сут на графике СКДО")
        self.dayline_chk.setChecked(True)
        group_layout.addWidget(self.dayline_chk)

        self.oadev_chk = QCheckBox("СКДО с перекрытиями")
        self.oadev_chk.setChecked(True)
        group_layout.addWidget(self.oadev_chk)

        self.alltau_chk = QCheckBox("СКДО за все интервалы измерения")
        self.alltau_chk.setChecked(True)
        group_layout.addWidget(self.alltau_chk)

        # group_layout.addWidget(QLabel("Median Filter Window Size:"))
        # self.filter_size = QComboBox()
        # self.filter_size.addItems(["3", "5", "7", "9", "11", "13", "15"])
        # self.filter_size.setCurrentIndex(2)  # Default to 7
        # group_layout.addWidget(self.filter_size)
        
        # group_layout.addWidget(QLabel("Clock Offset Unit:"))
        # self.unit_combo = QComboBox()
        # self.unit_combo.addItems(["Seconds", "Microseconds", "Nanoseconds"])
        # self.unit_combo.setCurrentIndex(2)  # Default to microseconds
        # group_layout.addWidget(self.unit_combo)
        
        layout.addWidget(group)

    def create_action_buttons(self, layout):
        button_layout = QHBoxLayout()
        
        #self.download_button = QPushButton("Download SP3 Files")
        self.download_button = QPushButton("Загрузить файлы SP3")
        self.download_button.clicked.connect(self.sync_sp3_files)
        self.download_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.download_button)
        
        #self.process_button = QPushButton("Process SP3 Files")
        self.process_button = QPushButton("Обработать файлы SP3")
        self.process_button.clicked.connect(self.process_files)
        self.process_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.process_button)
        
        #self.plot_button = QPushButton("Show Plot")
        self.plot_button = QPushButton("Графики")
        self.plot_button.clicked.connect(self.show_plot)
        self.plot_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.plot_button.setEnabled(False)
        button_layout.addWidget(self.plot_button)
        
        layout.addLayout(button_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select SP3 Files Folder", 
            self.folder_entry.text()
        )
        if folder:
            self.folder_entry.setText(folder)

    def apply_preset(self):
        idx = self.preset_combo.currentIndex()
        satellites = self.preset_combo.itemData(idx)
        self.sat_entry.setText(", ".join(satellites))

    def parse_filename_date(self, filename):
        """Extract date from RefWWWWD.sp3 filename format"""
        if self.ref02_chk.isChecked():
            match = re.search(r'Ref02(\d{4})(\d)\.sp3$', filename, re.IGNORECASE)
        else:
            match = re.search(r'\D{3}(\d{4})(\d)\.sp3$', filename, re.IGNORECASE)

        if match:
            week = int(match.group(1))
            day = int(match.group(2))
            
            # GPS epoch is January 6, 1980
            gps_epoch = datetime(1980, 1, 6)
            
            # Calculate date from GPS week and day
            total_days = week * 7 + day
            return gps_epoch + timedelta(days=total_days)
        return None

    def parse_sp3_file(self, file_path, prev_epoch):
        """Parse an SP3 file and extract satellite clock offset data"""
        data = {}
        current_epoch = prev_epoch       
        
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    # Parse epoch line
                    if line.startswith('*'):
                        # Format: "*  2023 12 31 23 45  0.00000000"
                        prev_epoch = current_epoch
                        parts = line.split()
                        year, month, day = int(parts[1]), int(parts[2]), int(parts[3])
                        hour, minute = int(parts[4]), int(parts[5])
                        second = float(parts[6])
                        current_epoch = datetime(year, month, day, hour, minute, int(second))                        
                    
                    # Parse satellite data line
                    elif line.startswith('P') & (current_epoch > prev_epoch):
                        parts = line.split()
                        sat_id = parts[0][1:]  # Remove 'P' prefix
                        
                        # The clock offset is the 5th value (index 4) in the line
                        if len(parts) >= 5:
                            try:
                                clock_offset = float(parts[4])*1e-6
                                if sat_id not in data:
                                    data[sat_id] = {'time': [], 'offset': []}
                                data[sat_id]['time'].append(current_epoch)
                                data[sat_id]['offset'].append(clock_offset)
                            except ValueError:
                                continue
            return data, current_epoch
        except Exception as e:
            #QMessageBox.warning(self, "File Error", f"Error parsing {os.path.basename(file_path)}:\n{str(e)}")
            QMessageBox.warning(self, "Ошибка файла", f"Ошибка парсинга файла {os.path.basename(file_path)}:\n{str(e)}")
            return {}

    def detrend(self, t, x, n=1):
        #t = np.arange(len(x))*30
        c = np.polyfit(t, x, n)
        #print(c[0]*86400)
        x -= np.polyval(c, t)
        return c

    def remove_trend(self, times, offsets, k = 1):
        """Remove linear trend from data using least squares"""
        # Convert times to seconds since first epoch
        t0 = times[0]
        t_sec = np.array([(t - t0).total_seconds() for t in times])
        
        # # Perform linear regression
        # A = np.vstack([t_sec, np.ones(len(t_sec))]).T
        # slope, intercept = np.linalg.lstsq(A, offsets, rcond=None)[0]
        
        # # Calculate and remove trend
        # trend = slope * t_sec + intercept
        # return offsets - trend, slope, intercept
        detrended = np.copy(offsets)
        c = self.detrend(t_sec, detrended, k)
        return detrended, c[0], c[1]
       
    def median_outlier_filter(self, data, window_size, threshold=5.0):
        """
        Apply a median-based outlier filter to time series data.
        
        Points that exceed threshold * MAD from the window median are replaced with the window median.
        
        Args:
            data (array-like): Input time series data
            window_size (int): Size of the sliding window (must be odd)
            threshold (float): Threshold in multiples of MAD (default: 5.0)
        
        Returns:
            np.ndarray: Filtered data array
        """
        if window_size % 2 == 0:
            raise ValueError("Window size must be odd")
        
        n = len(data)
        half_window = window_size // 2
        filtered = np.array(data, dtype=float).copy()
        
        # Pad the data at boundaries
        padded = np.pad(filtered, (half_window, half_window), mode='edge')
        
        for i in range(half_window, n + half_window):
            # Extract window centered at current point
            window = padded[i - half_window:i + half_window + 1]
            
            # Calculate median and MAD
            median = np.median(window)
            deviations = np.abs(window - median)
            mad = np.median(deviations)
            
            # Handle case where MAD is zero (constant values)
            if mad == 0:
                mad = 1e-9  # Small epsilon to avoid division by zero
            
            # Calculate current point's deviation
            current_val = padded[i]
            deviation = np.abs(current_val - median)
            
            # Replace if exceeds threshold * MAD
            if deviation > threshold * mad:
                filtered[i - half_window] = median
        
        return filtered

    def sync_sp3_files(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
    
        ftp_host = 'ftp.glonass-iac.ru'
        ftp_folder = '/MCC/PRODUCTS/Attestat/SP3/2025'  # Leave empty for root directory
        local_folder = './sp3_files'  # Local directory to store files
        
        # Ensure local directory exists
        os.makedirs(local_folder, exist_ok=True)
        
        # Get list of existing local files
        local_files = set()
        for f in os.listdir(local_folder):
            if f.lower().endswith('.sp3'):
                local_files.add(f)
        
        try:
            # Connect to FTP server
            print(f"Connecting to FTP server: {ftp_host}")
            with ftplib.FTP(ftp_host) as ftp:
                ftp.login()
                print("Connected successfully")
                
                # Change to the target directory
                if ftp_folder:
                    print(f"Changing to remote directory: {ftp_folder}")
                    ftp.cwd(ftp_folder)
                
                # Get list of remote files
                remote_files = []
                ftp.retrlines('NLST', remote_files.append)
                
                # Filter for .sp3 files (case insensitive)
                remote_sp3_files = [f for f in remote_files if f.lower().endswith('.sp3')]
                
                # Find new files that don't exist locally
                new_files = set(remote_sp3_files) - local_files
                
                if not new_files:
                    print("No new .sp3 files found on the server.")
                    #QApplication.restoreOverrideCursor()
                    #QMessageBox.information(self, "Download Complete", "No new .sp3 files found on the server.")
                    #QMessageBox.information(self, "Загрузка завершена", "Не найдено новых файлов .sp3.")
                    #return
                
                print(f"Found {len(new_files)} new .sp3 file(s) to download:")
                
                # Download each new file
                for filename in new_files:
                    local_path = os.path.join(local_folder, filename)
                    print(f"Downloading {filename}...")
                    
                    try:
                        with open(local_path, 'wb') as f:
                            ftp.retrbinary(f'RETR {filename}', f.write)
                        
                        # Verify file was downloaded
                        if os.path.exists(local_path):
                            file_size = os.path.getsize(local_path)
                            print(f"Successfully downloaded {filename} ({file_size} bytes)")
                        else:
                            print(f"Warning: Download may have failed for {filename}")
                    
                    except Exception as e:
                        print(f"Error downloading {filename}: {str(e)}")
                        # Clean up partially downloaded file if it exists
                        if os.path.exists(local_path):
                            os.remove(local_path)
        
        except ftplib.all_errors as e:
            print(f"FTP error: {str(e)}")
        except Exception as e:
            print(f"Error: {str(e)}")
                
        
        local_folder = './sp3_rapid'  # Local directory to store files
        os.makedirs(local_folder, exist_ok=True)

        latest_date = None
        for filename in os.listdir(local_folder):
            if filename.lower().endswith(('.sp3', '.sp3.z', '.sp3.gz')):
                file_date = self.parse_filename_date(filename)
                if file_date and (latest_date is None or file_date > latest_date):
                    latest_date = file_date

        end_date = datetime.now().date() - timedelta(days=1)  # Yesterday        
        if latest_date:
            start_date = latest_date + timedelta(days=1)
            print(f"Resuming download from {start_date} (after latest local file)")        
        else:
            start_date = end_date - timedelta(days=6)  # Default to 360 days back
            print(f"No local files found. Starting download from {start_date} (6 days ago)")
        
        if start_date > end_date:
            print("No new dates to process (start date after end date)")
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Загрузка завершена", "Все новые файлы загружены с FTP-сервера")
            return
    
        # Download new files
        try:
            # Connect to FTP server
            print(f"Connecting to FTP server: {ftp_host}")
            with ftplib.FTP(ftp_host) as ftp:
                ftp.login()
                print("Connected successfully")
                current_date = start_date
                while current_date <= end_date:
                    yy = current_date.strftime("%y")         # Last two digits of year
                    ddd = current_date.strftime("%j")        # Day of year (3 digits)
                    remote_dir = f"/MCC/PRODUCTS/{yy}{ddd}/rapid"
                    
                    try:
                        ftp.cwd(remote_dir)
                        files = ftp.nlst()
                        
                        for filename in files:
                            if not filename.lower().endswith(('.sp3')):
                                continue
                            
                            local_path = os.path.join(local_folder, filename)
                            if os.path.exists(local_path):
                                continue  # Skip existing files
                            
                            try:
                                with open(local_path, 'wb') as f:
                                    ftp.retrbinary(f"RETR {filename}", f.write)
                                print(f"Downloaded: {filename}")
                            except Exception as e:
                                print(f"Failed to download {filename}: {str(e)}")
                                if os.path.exists(local_path):
                                    os.remove(local_path)  # Clean up partial download
                    
                    except ftplib.all_errors as e:
                        if '550' in str(e):
                            pass  # Directory doesn't exist, skip
                        else:
                            print(f"FTP error for {current_date}: {str(e)}")
                    except Exception as e:
                        print(f"Error processing {current_date}: {str(e)}")
                    
                    current_date += timedelta(days=1)
                    
        except ftplib.all_errors as e:
            print(f"FTP error: {str(e)}")
        except Exception as e:
            print(f"Error: {str(e)}")
       
        print("Download completed")
        
        #QMessageBox.information(self, "Download Complete", "Files have been downloaded from FTP-server")
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Загрузка завершена", "Все новые файлы загружены с FTP-сервера")
    

    def process_files(self):        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # Get user inputs
        self.sp3_folder = self.folder_entry.text()
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        sat_list = [sat.strip().upper() for sat in self.sat_entry.text().split(',') if sat.strip()]
        window_size = 7#int(self.filter_size.currentText())
        
        # Validate inputs
        if not os.path.exists(self.sp3_folder):
            #QMessageBox.critical(self, "Error", f"Folder not found: {self.sp3_folder}")
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Ошибка", f"Каталог не найден: {self.sp3_folder}")            
            return
        
        if end_date < start_date:
            #QMessageBox.critical(self, "Error", "End date must be after start date")
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Ошибка", "Конечная дата не может быть раньше начальной")
            return
        
        if not sat_list:
            #QMessageBox.critical(self, "Error", "Enter at least one satellite")
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Ошибка", "Укажите хотя бы один спутник")
            return
        
        # Find SP3 files in the date range
        sp3_files = []
        self.mindate = end_date
        self.maxdate = start_date
        for filename in os.listdir(self.sp3_folder):
            if filename.lower().endswith('.sp3'):
                file_date = self.parse_filename_date(filename)
                if file_date and (start_date <= file_date.date() <= end_date):
                    sp3_files.append((file_date, os.path.join(self.sp3_folder, filename)))
                    if self.mindate > file_date.date():
                        self.mindate = file_date.date()
                    if self.maxdate < file_date.date():
                        self.maxdate = file_date.date()
        
        if not sp3_files:
            #QMessageBox.information(self, "No Files", 
            #                       "No SP3 files found in the selected date range")
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Нет файлов", 
                                   "Файлы SP3 не найдены для выбранных дат" + self.sp3_folder)
            return
        
        # Sort files by date
        sp3_files.sort(key=lambda x: x[0])
        
        # Process each file
        self.data = {sat: {'time': [], 'offset': []} for sat in sat_list}
        prev_epoch = datetime(1980, 1, 6)
        
        for file_date, file_path in sp3_files:
            # Parse SP3 file
            file_data, prev_epoch = self.parse_sp3_file(file_path, prev_epoch)
            
            # Collect data for selected satellites
            for sat in sat_list:
                if sat in file_data:
                    self.data[sat]['time'].extend(file_data[sat]['time'])
                    self.data[sat]['offset'].extend(file_data[sat]['offset'])
        
        # Process data for each satellite
        for sat in sat_list:
            if not self.data[sat]['time']:
                continue  # Skip satellites with no data
            
            # Sort data by time
            #sorted_indices = np.argsort(self.data[sat]['time'])
            #times = np.array(self.data[sat]['time'])[sorted_indices]
            #offsets = np.array(self.data[sat]['offset'])[sorted_indices]
            times = np.array(self.data[sat]['time'])

            self.phaselim = int(self.phaselim_entry.text())

            if self.glue_chk.isChecked():
                tmp = np.copy(self.data[sat]['offset'])
                n = len(tmp)
                delta = 0
                for i in range(n-1):
                    tmp_delta = tmp[i+1] - tmp[i]                
                    if np.abs(tmp_delta) > self.phaselim*1e-12:
                        delta += tmp_delta    
                        print(tmp_delta)
                    self.data[sat]['offset'][i+1] -= delta

            offsets = np.array(self.data[sat]['offset'])
            
            filtered = self.median_outlier_filter(offsets, window_size)
            # Remove linear trend
            #detrended, slope, intercept = self.remove_linear_trend(times, offsets)
            detrended, slope, intercept = self.remove_trend(times, filtered, 1)
            dedrifted, slope, intercept = self.remove_trend(times, filtered, 2)
            
            # Apply median filter
            #filtered = self.median_outlier_filter(detrended, window_size)
            
            # Store processed data
            self.data[sat]['detrended'] = detrended
            self.data[sat]['dedrifted'] = dedrifted
            self.data[sat]['detrend_slope'] = slope
            self.data[sat]['detrend_intercept'] = intercept
            self.data[sat]['filtered'] = filtered
            self.data[sat]['times'] = times
        
        # Enable plot button
        self.plot_button.setEnabled(True)
        #QMessageBox.information(self, "Processing Complete", 
        #                       f"Processed data for {len([sat for sat in sat_list if sat in self.data and 'detrended' in self.data[sat]])} satellites")
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Обработка завершена", 
                               f"Данные обработаны для {len([sat for sat in sat_list if sat in self.data and 'detrended' in self.data[sat]])} спутников")

    def show_plot(self):
        if not self.data:
            #QMessageBox.warning(self, "No Data", "Process data first before plotting")
            QMessageBox.warning(self, "Нет данных", "Необходимо обработать данные перед отрисовкой")
            return
        
        # Create plot window if it doesn't exist
        # if self.plot_phase_detrended is None or not self.plot_phase_detrended.isVisible():
        #     self.plot_phase_detrended = PlotWindow()
        # if self.plot_phase_dedrifted is None or not self.plot_phase_dedrifted.isVisible():
        #     self.plot_phase_dedrifted = PlotWindow()
        # if self.plot_freq is None or not self.plot_freq.isVisible():
        #     self.plot_freq = PlotFreq()
        # if self.plot_adev is None or not self.plot_adev.isVisible():
        #     self.plot_adev = PlotADEV()
        
        # Get unit conversion factor
        unit = "nanoseconds" #self.unit_combo.currentText().lower()
        if unit == "microseconds":
            factor = 1e6
            #unit_label = "μs"
            unit_label = "мкс"
        elif unit == "nanoseconds":
            factor = 1e9
            #unit_label = "ns"
            unit_label = "нс"
        else:  # seconds
            factor = 1
            #unit_label = "s"
            unit_label = "с"

        #self.plot_phase_detrended.append(PlotWindow())

        if self.phaseplot_chk.isChecked():
            self.pltcnt += 1   
            self.plot_phase_dedrifted.append(PlotWindow())
            self.plot_phase_dedrifted[self.pltcnt].plot_data(self.data, factor, unit_label, 'dedrifted', "Отклонение шкалы за исключением квадратичного тренда")
            self.plot_phase_dedrifted[self.pltcnt].show()       

        if self.freqplot_chk.isChecked():
            self.fpltcnt += 1
            self.plot_freq.append(PlotFreq())
            self.plot_freq[self.fpltcnt].plot_data(self.data)
            self.plot_freq[self.fpltcnt].show()

        if self.adevplot_chk.isChecked():
            self.adevcnt += 1
            self.plot_adev.append(PlotADEV())
            self.plot_adev[self.adevcnt].plot_data(self.data, self.drift_chk.isChecked(), self.oadev_chk.isChecked(), self.alltau_chk.isChecked(), self.dayline_chk.isChecked(), ", "+str(self.mindate)+" - "+str(self.maxdate))
            self.plot_adev[self.adevcnt].show()

        if self.psdplot_chk.isChecked():
            self.psdcnt += 1
            self.plot_psd.append(PlotPSD())
            self.plot_psd[self.psdcnt].plot_data(self.data, ", "+str(self.mindate)+" - "+str(self.maxdate))
            self.plot_psd[self.psdcnt].show()
        
        # Plot data for each satellite
        #self.plot_phase_detrended[self.pltcnt].plot_data(self.data, factor, unit_label, 'detrended', "Отклонение шкалы за исключением линейного тренда")
        #self.plot_phase_detrended[self.pltcnt].show()
        
class PlotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS Satellite Clock Offset")
        self.setGeometry(200, 200, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, central_widget)
        layout.addWidget(self.toolbar)
        
        # Initialize plot
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Clock Offset")
    
    def plot_data(self, data, conversion_factor, unit_label, datatype='detrended', title = "Satellite Clock Offset (Detrended and Filtered)"):
        # Clear previous plot
        self.ax.clear()
        
        # Plot data for each satellite
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
        
        legend_handles = []
        for i, (sat, sat_data) in enumerate(data.items()):
            if datatype not in sat_data:
                continue
            
            # Convert processed data to desired unit
            phase = sat_data[datatype] * conversion_factor
            #processed = sat_data['original_offsets'] * conversion_factor
            
            # Plot processed data
            color = colors[i % len(colors)]
            line, = self.ax.plot(sat_data['times'], phase, 
                                label=sat, color=color, linewidth=1.5)
            legend_handles.append(line)
                    
        # Set plot properties
        if legend_handles:
            self.ax.legend(handles=legend_handles, loc='best')
            self.ax.set_title(title)
            self.ax.set_ylabel(f"отклонение шкалы ({unit_label})")
            
            # Format x-axis as dates
            self.figure.autofmt_xdate()
        
        self.ax.grid(True)
        #self.ax.set_yticks([-0.2, -0.1, 0, 0.1, 0.2])
        # Redraw canvas        
        self.canvas.draw()
        
class PlotFreq(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS Satellite Frequency Offset")
        #self.setWindowTitle("Отклонение по частоте бортовых часов")
        self.setGeometry(200, 200, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, central_widget)
        layout.addWidget(self.toolbar)
        
        # Initialize plot
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        # self.ax.set_xlabel("Time")
        # self.ax.set_ylabel("Frequency Offset")
        self.ax.set_xlabel("Время")
        self.ax.set_ylabel("Отклонение по частоте")
            
    def plot_data(self, data):
        # Clear previous plot
        self.ax.clear()
        
        # Plot data for each satellite
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
        
        legend_handles = []
        for i, (sat, sat_data) in enumerate(data.items()):            
            if 'filtered' not in sat_data:
                continue
                        
            t = sat_data['times']
            x = sat_data['filtered']
            delta = t[1] - t[0]
            dt = delta.total_seconds()
            #kdec = 120
            kdec = int(3600/dt)
            time_delta = t[kdec:]-t[:-kdec]
            dts = [time_delta[i].total_seconds() for i in range(0, len(time_delta))]
            y = (x[kdec:]-x[:-kdec])/dts
            #ind = np.argwhere(np.abs(y)<3.e-13)
            ind = np.argwhere(y>-1.e-13)
            ind = ind.reshape(-1)            
            ind = np.arange(len(y))
            #y = (x[kdec:]-x[:-kdec])/30/kdec            
            
            t0 = t[0]
            t_sec = np.array([(ti - t0).total_seconds() for ti in t[:-kdec]])
            c = np.polyfit(t_sec[ind], y[ind], 1)
            #print(c[0]*86400)
            
            # Plot processed data
            color = colors[i % len(colors)]
            line, = self.ax.plot(t[ind], y[ind], #t[:-kdec], y, 
                                label=sat + f" Дрейф частоты: {c[0]*86400:.2e} / сут.", color=color, linewidth=1.5)
            legend_handles.append(line)
            tt = np.array([t_sec[0], t_sec[ind[-1]]])
            yy = c[0]*tt + c[1]
            line, = self.ax.plot([t[0], t[ind[-1]]], yy, '--', color=color, linewidth=1.5)
                    
        # Set plot properties
        if legend_handles:
            self.ax.legend(handles=legend_handles, loc='best')
            # self.ax.set_title("Satellite Frequency Offset")
            # self.ax.set_ylabel(f"Frequency Offset")
            self.ax.set_title(r"Относительная разность частот в скользящем окне $\tau$ = 1 час")
            self.ax.set_ylabel(f"отклонение по частоте")
            
            # Format x-axis as dates
            self.figure.autofmt_xdate()
        
        # Redraw canvas
        self.canvas.draw()


class PlotADEV(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS Satellite Clock ADEV")
        self.setGeometry(200, 200, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, central_widget)
        layout.addWidget(self.toolbar)
        
        # Initialize plot
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_xlabel("Интервал времени измерения, с")
        self.ax.set_ylabel("СКДО")
    
    def generate_tau(self):
    
        tau = np.arange(1,10)
        tau = np.append(tau, np.arange(10,100,10))
        tau = np.append(tau, np.arange(100,1000,100))
        tau = np.append(tau, np.arange(1000,10000,1000))
        tau = np.append(tau, np.arange(10000,100000,10000))
        tau = np.append(tau, np.arange(100000,1000000,100000))
        tau = np.append(tau, np.arange(1000000,10000000,1000000))
  
        return tau
    
    def plot_data(self, data, is_dedrift=True, overlap=True, alltau=True, show_day_lines=True, dates=""):
        # Clear previous plot
        self.ax.clear()
        
        # Plot data for each satellite
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
        
        legend_handles = []
        for i, (sat, sat_data) in enumerate(data.items()):
            if 'filtered' not in sat_data:
                continue
            
            # Convert processed data to desired unit
            if is_dedrift:
                x = sat_data['dedrifted']
            else:
                x = sat_data['filtered']
            
            delta = sat_data['times'][1] - sat_data['times'][0]
            dt = delta.total_seconds()
            print(dt)

            if alltau:
                tau_arr = np.arange(1, 300000)
                mrk = ''
            else:
                tau_arr = self.generate_tau()
                tau_arr = np.append(tau_arr, 3600)
                tau_arr = np.append(tau_arr, 86400)
                tau_arr = np.sort(tau_arr)
                mrk = '.'
            
            if overlap:
                taus, adevs, err, ns = allan.oadev(x, rate=1/dt, taus=tau_arr)                 
            else:
                taus, adevs, err, ns = allan.adev(x, rate=1/dt, taus=tau_arr)                 
          
            # Plot processed data
            color = colors[i % len(colors)]            

            ind = np.where(taus == 3600)
            adev_day = ""
            if len(ind) > 0:
                if len(ind[0]) > 0:
                    adev_day = f", СКДО(1 ч.) = {adevs[ind[0][0]]:.2e}"            

            ind = np.where(taus == 86400)                        
            if len(ind) > 0:
                if len(ind[0]) > 0:
                    adev_day += f", СКДО(1 сут.) = {adevs[ind[0][0]]:.2e}"            
            
            line, = self.ax.loglog(taus, adevs, 
                                label=sat+adev_day, color=color, linewidth=1.5, marker = mrk)
            legend_handles.append(line)
        
        self.ax.grid(True, which="both", ls="--")        
                    
        # Set plot properties
        if legend_handles:
            self.ax.legend(handles=legend_handles, loc='best')
            if is_dedrift:
                self.ax.set_title("Нестабильность частоты с исключенным дрейфом"+dates)
            else:
                self.ax.set_title("Нестабильность частоты без исключения дрейфа"+dates)
            self.ax.set_xlabel("Интервал времени измерения, с")
            self.ax.set_ylabel("СКДО")
            
            # Format x-axis as dates
            #self.figure.autofmt_xdate()
        
        # Redraw canvas
        if show_day_lines:
            self.ax.loglog([86400, 86400], self.ax.get_ylim(), 'r--')
            #self.ax.loglog(self.ax.get_xlim(), [5e-15, 5e-15], 'r--')            

        self.canvas.draw()  
           

class PlotPSD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNSS Satellite Clock PSD")
        self.setGeometry(200, 200, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, central_widget)
        layout.addWidget(self.toolbar)
        
        # Initialize plot
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_xlabel("Частота, мГц")
        self.ax.set_ylabel("СПМ, дБн/Гц")       

        N, beta = kaiserord(40, 0.02)
        self.taps = firwin(N, 0.1, window=('kaiser', beta)) 
    
    def fft(self, x):
        n = x.size
        _x = detrend(x)
        w = np.hanning(n)
        for i in range(n):
            _x[i] *= w[i]
        fft = np.fft.fft(_x)
        return fft
    
    def calculate(self, x, D):
        n = x.size
        psd = []
        P = (int)(np.floor(n / D))
        while P > 0:
            _psd = np.zeros(D, dtype='double')  # complex128
            _x = np.zeros(D, dtype='double')
            for p in range(P):
                _x = x[p*D:(p+1)*D:1]
                _psd += abs(self.fft(_x))**2
            psd.append(_psd / (float)(P))
            filtered_x = lfilter(self.taps, 1.0, x)
            x = filtered_x[::10]
            n = x.size
            P = (int)(np.floor(n / D))

        return psd
    
    def plot_data(self, data, dates=""):
        # Clear previous plot
        self.ax.clear()
        
        # Plot data for each satellite
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
                
        legend_handles = []
        for i, (sat, sat_data) in enumerate(data.items()):
            if 'filtered' not in sat_data:
                continue
            
            # Plot processed data
            color = colors[i % len(colors)]
            
            x = sat_data['dedrifted']            
            dt = 30

            D = 512

            sf = self.calculate(x, D)
            f0 = 5e6
            mult = 10 * np.pi**2 * f0**2 / D
            self.ax.set_xscale('log')
            Lf_arr = []
            f_arr = []
            for j in range(len(sf)):
                f_up = 1/2/dt
                buf = np.arange(D)
                bool_f = (buf >= D/30) & (buf < D/2)
                ind_f = buf[bool_f]
                f = ind_f * f_up/D * 2              
                lg_f = np.log(f)/np.log(10)
                f_arr.append(f)
                Lf_arr.append(10*np.log(mult*sf[j][bool_f]*dt)/np.log(10))                
                dt *= 10
            
            f_arr = np.array(f_arr)
            Lf_arr = np.array(Lf_arr)
            f_arr = np.reshape(f_arr, -1)
            Lf_arr = np.reshape(Lf_arr, -1)
            sorted_indices = np.argsort(f_arr)
            line, = self.ax.plot(f_arr[sorted_indices]*1000, Lf_arr[sorted_indices], label=sat, color=color)
            legend_handles.append(line)
        
        self.ax.grid(True, which="both", ls="--")        
                    
        # Set plot properties
        if legend_handles:
            self.ax.legend(handles=legend_handles, loc='best')
            self.ax.set_title("Спектральная плотность мощности фазового шума для 5 МГц"+dates)
            self.ax.set_xlabel("Частота, мГц")
            self.ax.set_ylabel("СПМ, дБн/Гц")
            
        self.canvas.draw()        


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern style
    
    # Set application styles
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            margin-top: 1ex;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }
        QPushButton {
            padding: 5px 15px;
            border-radius: 4px;
        }
    """)
    
    processor = SP3Processor()
    processor.show()
    sys.exit(app.exec_())