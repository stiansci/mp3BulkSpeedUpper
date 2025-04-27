import sys
import subprocess
import os
import tempfile
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                            QLineEdit, QFileDialog, QVBoxLayout, 
                            QHBoxLayout, QWidget, QComboBox, QMessageBox,
                            QProgressBar, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent

class ConversionThread(QThread):
    conversion_done = pyqtSignal(str)
    preview_done = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # current, total
    file_converted = pyqtSignal(str)

    def __init__(self, input_files, speed_factor, output_folder, is_preview=False, replace_original=False):
        super().__init__()
        self.input_files = input_files
        self.speed_factor = speed_factor
        self.output_folder = output_folder
        self.is_preview = is_preview
        self.replace_original = replace_original

    def run(self):
        if not self.is_preview:
            os.makedirs(self.output_folder, exist_ok=True)
        
        total_files = len(self.input_files)
        
        for index, input_file in enumerate(self.input_files):
            if not os.path.exists(input_file):
                continue
                
            if self.is_preview:
                # Per la preview, usiamo un file temporaneo
                output_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            else:
                output_file = os.path.join(self.output_folder, os.path.basename(input_file))
            
            try:
                subprocess.run([
                    'ffmpeg', 
                    '-i', input_file, 
                    '-filter:a', f'atempo={self.speed_factor}', 
                    '-y',  # Sovrascrivi il file se esiste
                    output_file
                ], check=True)
                
                if self.is_preview:
                    self.preview_done.emit(output_file)
                else:
                    # Se l'opzione di sostituzione è attiva, sostituisci il file originale
                    if self.replace_original and not self.is_preview:
                        try:
                            shutil.copy2(output_file, input_file)
                            print(f"File originale sostituito: {input_file}")
                        except Exception as e:
                            print(f"Errore durante la sostituzione del file originale: {e}")
                    
                    print(f"Conversione completata per {input_file}")
                    self.file_converted.emit(os.path.basename(input_file))
                
                # Aggiorna la barra di progresso
                self.progress_update.emit(index + 1, total_files)
                
            except subprocess.CalledProcessError as e:
                print(f"Errore durante la conversione: {e}")
                # Aggiorna comunque la barra di progresso in caso di errore
                self.progress_update.emit(index + 1, total_files)
        
        if not self.is_preview:
            print("Tutti i file sono stati convertiti.")
            self.conversion_done.emit(self.output_folder)


class DropArea(QWidget):
    files_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        # Styling per l'area di drop
        self.setStyleSheet("""
            DropArea {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f8f8f8;
                min-height: 80px;
            }
            DropArea:hover {
                border-color: #3498db;
                background-color: #e8f4fc;
            }
        """)
        
        # Layout per il contenuto dell'area di drop
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Trascina qui i file MP3")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        self.file_count_label = QLabel("")
        self.file_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.file_count_label)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Verifica che almeno un file sia MP3
            has_mp3 = False
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.mp3'):
                    has_mp3 = True
                    break
            
            if has_mp3:
                event.acceptProposedAction()
                self.setStyleSheet("""
                    DropArea {
                        border: 2px dashed #3498db;
                        border-radius: 5px;
                        background-color: #e8f4fc;
                        min-height: 80px;
                    }
                """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropArea {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f8f8f8;
                min-height: 80px;
            }
            DropArea:hover {
                border-color: #3498db;
                background-color: #e8f4fc;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.mp3'):
                files.append(file_path)
        
        if files:
            self.files_dropped.emit(files)
            self.file_count_label.setText(f"{len(files)} file MP3 selezionati")
        
        self.setStyleSheet("""
            DropArea {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f8f8f8;
                min-height: 80px;
            }
            DropArea:hover {
                border-color: #3498db;
                background-color: #e8f4fc;
            }
        """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Anki Audio Speed Upper")
        self.setGeometry(100, 100, 500, 550)

        # Layout principale
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # Area di drag & drop
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.handle_dropped_files)
        main_layout.addWidget(self.drop_area)

        # Sezione selezione file
        file_layout = QVBoxLayout()
        
        self.btn_select_file = QPushButton("Seleziona File MP3")
        self.btn_select_file.clicked.connect(self.select_input_files)
        file_layout.addWidget(self.btn_select_file)

        self.input_file_label = QLabel("Oppure inserisci il percorso del file:")
        file_layout.addWidget(self.input_file_label)

        self.input_file_path = QLineEdit()
        file_layout.addWidget(self.input_file_path)

        self.selected_files_label = QLabel("Nessun file selezionato")
        file_layout.addWidget(self.selected_files_label)

        main_layout.addLayout(file_layout)

        # Sezione velocità
        speed_layout = QVBoxLayout()
        speed_label = QLabel("Seleziona fattore di velocità:")
        speed_layout.addWidget(speed_label)

        speed_selector_layout = QHBoxLayout()
        
        self.speed_combo = QComboBox()
        speeds = ["1.25x", "1.5x", "1.75x", "1.84x", "2.0x", "2.5x", "3.0x"]
        self.speed_combo.addItems(speeds)
        self.speed_combo.setCurrentText("1.84x")  # Default come nel codice originale
        speed_selector_layout.addWidget(self.speed_combo)
        
        speed_layout.addLayout(speed_selector_layout)
        main_layout.addLayout(speed_layout)

        # Sezione cartella di output
        output_layout = QHBoxLayout()
        output_label = QLabel("Cartella di output:")
        output_layout.addWidget(output_label)
        
        self.output_path = QLineEdit()
        default_output = os.path.join(os.path.expanduser("~"), "Downloads", "AudioSpeedUpper")
        self.output_path.setText(default_output)
        output_layout.addWidget(self.output_path)
        
        self.btn_browse_output = QPushButton("Sfoglia")
        self.btn_browse_output.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.btn_browse_output)
        
        main_layout.addLayout(output_layout)

        # Checkbox per sostituire i file originali
        self.replace_original_checkbox = QCheckBox("Sostituisci i file originali dopo la conversione")
        main_layout.addWidget(self.replace_original_checkbox)

        # Pulsanti di azione
        buttons_layout = QHBoxLayout()
        
        self.btn_preview = QPushButton("Crea Anteprima")
        self.btn_preview.clicked.connect(self.preview_audio)
        buttons_layout.addWidget(self.btn_preview)
        
        self.btn_convert = QPushButton("Converti")
        self.btn_convert.clicked.connect(self.convert_files)
        buttons_layout.addWidget(self.btn_convert)
        
        self.btn_restart = QPushButton("Riavvia")
        self.btn_restart.clicked.connect(self.restart_program)
        buttons_layout.addWidget(self.btn_restart)
        
        main_layout.addLayout(buttons_layout)

        # Barra di progresso
        progress_layout = QVBoxLayout()
        progress_label = QLabel("Progresso conversione:")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_detail_label = QLabel("")
        progress_layout.addWidget(self.progress_detail_label)
        
        main_layout.addLayout(progress_layout)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

        # Inizializzazione variabili
        self.selected_files = []
        self.preview_file = None

    def handle_dropped_files(self, files):
        self.selected_files = files
        num_files = len(files)
        self.selected_files_label.setText(f"{num_files} file selezionati")
        if num_files == 1:
            self.input_file_path.setText(files[0])
        self.status_label.setText(f"{num_files} file MP3 pronti per la conversione")

    def select_input_files(self):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("File MP3 (*.mp3)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if file_dialog.exec():
            self.selected_files = file_dialog.selectedFiles()
            num_files = len(self.selected_files)
            self.selected_files_label.setText(f"{num_files} file selezionati")
            if num_files == 1:
                self.input_file_path.setText(self.selected_files[0])
            self.drop_area.file_count_label.setText(f"{num_files} file MP3 selezionati")

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella di output")
        if folder:
            self.output_path.setText(folder)

    def get_speed_factor(self):
        speed_text = self.speed_combo.currentText()
        return float(speed_text.replace('x', ''))

    def get_input_files(self):
        # Priorità al campo di testo se contiene qualcosa
        input_file_path = self.input_file_path.text().strip()
        if input_file_path:
            return [input_file_path]
        return self.selected_files

    def update_progress(self, current, total):
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_detail_label.setText(f"Convertiti {current} di {total} file")

    def update_file_progress(self, filename):
        self.status_label.setText(f"Convertito: {filename}")

    def preview_audio(self):
        input_files = self.get_input_files()
        if not input_files:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un file audio.")
            return

        self.status_label.setText("Creazione anteprima in corso...")
        self.btn_preview.setEnabled(False)
        
        # Crea un thread per la conversione di anteprima
        speed_factor = self.get_speed_factor()
        preview_folder = os.path.join(os.path.expanduser("~"), "Downloads", "AudioSpeedUpper_Preview")
        os.makedirs(preview_folder, exist_ok=True)
        
        self.preview_thread = ConversionThread(
            input_files=[input_files[0]],  # Solo il primo file per l'anteprima
            speed_factor=speed_factor,
            output_folder=preview_folder,
            is_preview=True,
            replace_original=False  # Non sostituire mai l'originale per l'anteprima
        )
        self.preview_thread.preview_done.connect(self.open_preview)
        self.preview_thread.start()

    def open_preview(self, preview_file):
        self.preview_file = preview_file
        self.status_label.setText("Anteprima creata. Apertura del file...")
        
        # Apri il file con il player predefinito del sistema
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(preview_file))
            self.status_label.setText(f"Anteprima aperta nel player predefinito: {os.path.basename(preview_file)}")
        except Exception as e:
            self.status_label.setText(f"Errore nell'apertura dell'anteprima: {e}")
        
        # Riabilita il pulsante di anteprima
        self.btn_preview.setEnabled(True)

    def convert_files(self):
        input_files = self.get_input_files()
        if not input_files:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un file audio.")
            return

        output_folder = self.output_path.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "Attenzione", "Specifica una cartella di output.")
            return

        # Chiedi conferma se l'utente ha selezionato di sostituire i file originali
        replace_original = self.replace_original_checkbox.isChecked()
        if replace_original:
            reply = QMessageBox.question(
                self, 
                "Conferma sostituzione", 
                "Stai per sostituire i file audio originali. Questa operazione non può essere annullata. Continuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Reset della barra di progresso
        self.progress_bar.setValue(0)
        self.progress_detail_label.setText("Avvio conversione...")
        
        self.btn_convert.setEnabled(False)
        self.status_label.setText("Conversione in corso...")
        
        # Crea un thread per la conversione
        speed_factor = self.get_speed_factor()
        self.conversion_thread = ConversionThread(
            input_files=input_files,
            speed_factor=speed_factor,
            output_folder=output_folder,
            replace_original=replace_original
        )
        
        # Connetti i segnali per aggiornare la UI
        self.conversion_thread.progress_update.connect(self.update_progress)
        self.conversion_thread.file_converted.connect(self.update_file_progress)
        self.conversion_thread.conversion_done.connect(self.handle_conversion_done)
        
        self.conversion_thread.start()

    def handle_conversion_done(self, output_folder):
        self.btn_convert.setEnabled(True)
        
        replace_original = self.replace_original_checkbox.isChecked()
        if replace_original:
            self.status_label.setText("Conversione completata! I file originali sono stati sostituiti.")
        else:
            self.status_label.setText("Conversione completata!")
            
            # Chiedi all'utente se vuole aprire la cartella di output
            reply = QMessageBox.question(
                self, 
                "Conversione completata", 
                "Vuoi aprire la cartella di output?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(output_folder))
                except Exception as e:
                    print(f"Errore nell'apertura della cartella: {e}")

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
