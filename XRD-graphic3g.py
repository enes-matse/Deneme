# --- Standard imports ---
import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
# NOTE: Big Caslon is kept for historical reference; labels now use UI-selected fonts.
# Some fonts (like Big Caslon) lack Greek glyphs (e.g., θ), which previously caused warnings.
from matplotlib.font_manager import FontProperties
big_caslon_path = "/System/Library/Fonts/Supplemental/BigCaslon.ttf"
big_caslon_font = FontProperties(fname=big_caslon_path, size=40)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QPushButton, QVBoxLayout, QColorDialog, QFontDialog, QInputDialog,
    QFileDialog, QTabWidget, QHBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox, QSizePolicy, QCheckBox,
    QLineEdit, QLabel, QFontComboBox, QDoubleSpinBox, QComboBox, QScrollArea, QDialog, QStatusBar
)

# --- Manuel XRD veri girişi dialogu ---
class ManualDataEntryDialog(QDialog):
    """Manuel XRD veri girişi: isim, offset, renk ve X/Y tablosu (+ pano yapıştır / toplu temizle)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manuel XRD Veri Ekle")
        self.resize(900, 600)

        self.result_df = None
        self.result_filename = None
        self.result_offset = 0.0
        self.result_color = "#1f77b4"

        vbox = QVBoxLayout(self)

        # Üst form: isim, offset, renk
        form = QHBoxLayout()
        form.addWidget(QLabel("İsim:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Örn: Manual-XRD-1")
        form.addWidget(self.name_edit)

        form.addWidget(QLabel("Offset:"))
        self.offset_edit = QLineEdit("0.0")
        self.offset_edit.setFixedWidth(80)
        form.addWidget(self.offset_edit)

        form.addWidget(QLabel("Renk:"))
        self.color_btn = QPushButton("Seç")
        self.color_btn.clicked.connect(self.pick_color)
        form.addWidget(self.color_btn)

        form.addStretch()
        vbox.addLayout(form)

        # Veri tablosu
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["X (2θ)", "Y (Intensity)"])
        self.table.setRowCount(50)  # başlangıçta 50 boş satır
        vbox.addWidget(self.table)

        # Alt buton çubuğu
        h = QHBoxLayout()
        self.btn_add_row = QPushButton("Satır Ekle")
        self.btn_insert_row = QPushButton("Seçili Üstüne Ekle")
        self.btn_del_rows = QPushButton("Seçili Satır(ları) Sil")
        self.btn_paste = QPushButton("Panodan Yapıştır")
        self.btn_clear = QPushButton("Toplu Temizle")
        self.btn_apply = QPushButton("Uygula")
        self.btn_close = QPushButton("Kapat")
        h.addStretch()
        h.addWidget(self.btn_add_row)
        h.addWidget(self.btn_insert_row)
        h.addWidget(self.btn_del_rows)
        h.addWidget(self.btn_paste)
        h.addWidget(self.btn_clear)
        h.addWidget(self.btn_apply)
        h.addWidget(self.btn_close)
        vbox.addLayout(h)

        # Bağlantılar
        self.btn_add_row.clicked.connect(self.add_row)
        self.btn_insert_row.clicked.connect(self.insert_row_above)
        self.btn_del_rows.clicked.connect(self.delete_selected_rows)
        self.btn_paste.clicked.connect(self.paste_from_clipboard)
        self.btn_clear.clicked.connect(self.clear_table)
        self.btn_apply.clicked.connect(self.apply_data)
        self.btn_close.clicked.connect(self.reject)

    # --- Helpers ---
    def pick_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.result_color = c.name()
            self.color_btn.setStyleSheet(f"background-color: {self.result_color}")

    def add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(""))
        self.table.setItem(r, 1, QTableWidgetItem(""))

    def insert_row_above(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            self.add_row()
            return
        r0 = min(idx.row() for idx in sel)
        self.table.insertRow(r0)
        self.table.setItem(r0, 0, QTableWidgetItem(""))
        self.table.setItem(r0, 1, QTableWidgetItem(""))

    def delete_selected_rows(self):
        sel = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        for r in sel:
            self.table.removeRow(r)

    def paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        if not text or not text.strip():
            return
        rows = text.strip().splitlines()
        # Basit CSV/TSV/boşluk ayracı desteği
        for r, line in enumerate(rows):
            parts = [p for p in line.replace("\t", " ").replace(",", " ").split() if p]
            if len(parts) >= 2:
                if r >= self.table.rowCount():
                    self.table.insertRow(self.table.rowCount())
                self.table.setItem(r, 0, QTableWidgetItem(parts[0]))
                self.table.setItem(r, 1, QTableWidgetItem(parts[1]))

    def clear_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(50)

    def apply_data(self):
        # İsim
        name = (self.name_edit.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Eksik İsim", "Lütfen yeni XRD için bir isim girin.")
            return
        # Offset
        try:
            off = float(self.offset_edit.text().strip())
        except Exception:
            QMessageBox.warning(self, "Hatalı Offset", "Offset için geçerli bir sayı girin.")
            return
        # X/Y verileri
        xs, ys = [], []
        for r in range(self.table.rowCount()):
            ix = self.table.item(r, 0)
            iy = self.table.item(r, 1)
            if ix is None and iy is None:
                continue
            sx = ix.text().strip() if ix else ""
            sy = iy.text().strip() if iy else ""
            if sx == "" and sy == "":
                continue
            try:
                xval = float(sx)
                yval = float(sy)
            except Exception:
                QMessageBox.warning(self, "Geçersiz Hücre", f"{r+1}. satırda sayı olmayan değer var.")
                return
            xs.append(xval)
            ys.append(yval)
        if len(xs) < 2:
            QMessageBox.warning(self, "Yetersiz Veri", "En az iki nokta girin.")
            return
        # Sonuçları sakla ve kapat
        self.result_filename = name
        self.result_offset = off
        self.result_df = pd.DataFrame({0: xs, 1: ys})
        self.accept()
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.ticker as ticker
# --- Navigation Toolbar import ---
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
# --- Peak detection import ---
from scipy.signal import find_peaks, savgol_filter
from scipy import sparse
from scipy.sparse.linalg import spsolve
# --- AI trend analysis imports ---
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score


class RenkDegistirici(QMainWindow):
    def open_manual_data_dialog(self):
        """Manuel veri girişi dialogunu açar; onaylandığında yeni XRD dataset ekler."""
        dlg = ManualDataEntryDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_df is not None:
            if not hasattr(self, "xrd_datasets"):
                self.xrd_datasets = []

            # İsim çakışmasını engelle
            base_name = dlg.result_filename
            name = base_name
            counter = 2
            existing_names = {d.get("filename") for d in self.xrd_datasets}
            while name in existing_names:
                name = f"{base_name}-{counter}"
                counter += 1

            new_entry = {
                "filename": name,
                "df": dlg.result_df.copy(),
                "offset": dlg.result_offset,
                "color": getattr(dlg, "result_color", "#1f77b4"),
                "orig_df": dlg.result_df.copy()
            }
            self.xrd_datasets.append(new_entry)

            # Kontrol paneline satır ekle
            if hasattr(self, "add_control_row"):
                self.add_control_row(new_entry["filename"], new_entry["offset"], new_entry["color"])
            # Yeniden çiz
            self.redraw_plot()
            QMessageBox.information(self, "Eklendi", f"'{new_entry['filename']}' dataset'i eklendi.")
    def set_title_alignment(self):
        alignment, ok = QInputDialog.getItem(
            self,
            "Başlık Hizalaması",
            "Hizalama Seç:",
            ["Sol", "Orta", "Sağ"],
            editable=False
        )
        if not ok:
            return

        align_map = {"Sol": 0.0, "Orta": 0.5, "Sağ": 1.0}
        self.ax.title.set_position((align_map[alignment], 1.0))
        self.canvas.draw()
    def set_axis_font_style(self):
        options = ["Normal", "Kalın", "İtalik", "Kalın + İtalik"]
        choice, ok = QInputDialog.getItem(self, "Eksen Yazı Stili", "Stil Seç:", options, editable=False)
        if not ok:
            return

        weight = "normal"
        style = "normal"
        if "Kalın" in choice:
            weight = "bold"
        if "İtalik" in choice:
            style = "italic"

        self.ax.xaxis.label.set_fontweight(weight)
        self.ax.xaxis.label.set_fontstyle(style)
        self.ax.yaxis.label.set_fontweight(weight)
        self.ax.yaxis.label.set_fontstyle(style)
        self.canvas.draw()
    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "Hakkında",
            "XRD Görüntüleyici ve Analiz Aracı\nGeliştirici: Enes Ddn\nVersiyon: 1.0"
        )

    def show_howto_dialog(self):
        text = (
            "XRD Arka Plan / Smoothing Kullanım Kılavuzu\n"
            "\n"
            "1) Veri Yükleme:\n"
            "   - Dosya menüsünden veya üstteki 'Dosya Ekle' ile XRD verinizi (.txt) yükleyin.\n"
            "\n"
            "2) Ön İşleme menüsü:\n"
            "   - Yumuşat (Savitzky–Golay): Pencere (tek sayı) ve polinom derecesi seçin.\n"
            "     * Daha büyük pencere ⇒ daha güçlü yumuşatma (pikleri aşırı yuvarlamamaya dikkat).\n"
            "   - Arka Plan Çıkar (ALS): λ (düzlük), p (asimetrik ağırlık) ve iterasyon girin.\n"
            "     * λ ↑ ⇒ daha düz taban; tipik 1e5–1e7. p küçük (≈0.001–0.05) ⇒ tepe koruması artar.\n"
            "   - Arka Plan Çıkar (Rolling Min/Median): Pencere nokta sayısı verin, yöntem Min/Median.\n"
            "     * Amorf/fluoresans zemini takip etmek için geniş pencere kullanın.\n"
            "   - Arka Planı Göster/Gizle: Çıkarılan tabanı kesik gri eğri olarak aç/kapatır.\n"
            "   - Orijinale Dön: Tüm ön işlemleri geri alır.\n"
            "\n"
            "3) Çoklu Dataset:\n"
            "   - Ön işlemeyi uygularken 'Tüm Datasetler' veya tek bir dosya seçebilirsiniz.\n"
            "\n"
            "4) Eksen ve Legend Ayarları:\n"
            "   - Legends/Eksenler/Eksen Çizgileri menülerinden konum, yazı tipi, renk, kalınlık ve aralıkları ayrı ayrı ayarlayın.\n"
            "\n"
            "5) Dikey Çizgiler ve Grid:\n"
            "   - Çizgi Çekme menüsünden grid’i aç/kapatın; 2θ konum(lar)ına dikey çizgi ekleyin (örn: 10, 27.5, 43).\n"
            "\n"
            "6) Tema ve Kayıt:\n"
            "   - Üstteki Tema listesinden matplotlib temasını değiştirin.\n"
            "   - Kaydet ile görseli 600 dpi olarak dışa aktarın.\n"
        )
        QMessageBox.information(self, "Nasıl Kullanılır?", text)

    def compute_fwhm(self, x, y, peaks):
        """
        Compute the Full Width at Half Maximum (FWHM) for each peak index in peaks.
        x and y should be 1D arrays or Series.
        Returns a list of FWHM values (same order as peaks).
        """
        fwhm_list = []
        x_vals = x.values if hasattr(x, "values") else np.array(x)
        y_vals = y.values if hasattr(y, "values") else np.array(y)
        for peak_idx in peaks:
            peak_x = x_vals[peak_idx]
            peak_y = y_vals[peak_idx]
            half_max = peak_y / 2.0
            # Search to the left
            left_idx = peak_idx
            while left_idx > 0 and y_vals[left_idx] > half_max:
                left_idx -= 1
            # Interpolate x_left
            if left_idx != peak_idx and y_vals[left_idx] != y_vals[left_idx+1]:
                frac = (half_max - y_vals[left_idx]) / (y_vals[left_idx+1] - y_vals[left_idx])
                x_left = x_vals[left_idx] + frac * (x_vals[left_idx+1] - x_vals[left_idx])
            else:
                x_left = x_vals[left_idx]
            # Search to the right
            right_idx = peak_idx
            while right_idx < len(y_vals) - 1 and y_vals[right_idx] > half_max:
                right_idx += 1
            # Interpolate x_right
            if right_idx != peak_idx and y_vals[right_idx] != y_vals[right_idx-1]:
                frac = (half_max - y_vals[right_idx]) / (y_vals[right_idx-1] - y_vals[right_idx])
                x_right = x_vals[right_idx] + frac * (x_vals[right_idx-1] - x_vals[right_idx])
            else:
                x_right = x_vals[right_idx]
            fwhm = abs(x_right - x_left)
            fwhm_list.append(fwhm)
        return fwhm_list

    def export_peaks(self):
        try:
            if not hasattr(self, 'df') or self.df is None:
                QMessageBox.warning(self, "Uyarı", "Önce bir XRD verisi yükleyin.")
                return

            x = self.df.iloc[:, 0]
            y = self.df.iloc[:, 1]
            peaks, _ = find_peaks(y, height=np.max(y) * 0.1)

            if len(peaks) == 0:
                QMessageBox.information(self, "Bilgi", "Hiç tepe noktası bulunamadı.")
                return

            # Compute FWHM for each peak
            fwhm_values = self.compute_fwhm(x, y, peaks)

            peak_positions = x.iloc[peaks].reset_index(drop=True)
            peak_heights = y.iloc[peaks].reset_index(drop=True)
            # PDF matching
            matches = []
            for theta in peak_positions:
                matched = []
                for phase, ref_peaks in self.pdf_db.items():
                    for ref in ref_peaks:
                        if abs(theta - ref) <= 0.3:
                            matched.append(phase)
                            break
                matches.append(", ".join(matched) if matched else "-")

            peak_df = pd.DataFrame({
                "2θ": peak_positions,
                "Intensity": peak_heights,
                "FWHM": fwhm_values,
                "PDF Match": matches
            })

            # Add crystallinity classification based on FWHM thresholds
            crystallinity = []
            for f in fwhm_values:
                if f < 0.2:
                    crystallinity.append("Highly Crystalline")
                elif f < 0.5:
                    crystallinity.append("Moderately Crystalline")
                else:
                    crystallinity.append("Poorly Crystalline")
            peak_df["Crystallinity"] = crystallinity

            save_path, _ = QFileDialog.getSaveFileName(self, "Tepe Noktalarını Kaydet", "", "CSV Files (*.csv)")
            if save_path:
                peak_df.to_csv(save_path, index=False)
                QMessageBox.information(self, "Başarılı", "Tepe noktaları başarıyla kaydedildi.\n\nDosya FWHM, PDF eşleşmelerini ve kristalinlik sınıflandırmasını içerir.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tepe noktaları dışa aktarılırken hata oluştu:\n{str(e)}")

    def apply_theta_filter(self):
        try:
            tmin = float(self.theta_min.text())
            tmax = float(self.theta_max.text())
            if hasattr(self, 'df') and self.df is not None:
                self.df = self.df[(self.df.iloc[:, 0] >= tmin) & (self.df.iloc[:, 0] <= tmax)].reset_index(drop=True)
                self.update_graph_from_df()
        except ValueError:
            QMessageBox.warning(self, "Hatalı Giriş", "Lütfen geçerli bir 2θ aralığı girin.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"2θ filtrelemesi sırasında hata:\n{str(e)}")
    def save_theme(self):
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        dosya_yolu, _ = QFileDialog.getSaveFileName(self, "Tema Kaydet", "", "JSON Dosyası (*.json)")
        if not dosya_yolu:
            return
        theme = {
            "temp_color": self.temp_line.get_color(),
            "disp_color": self.disp_line.get_color(),
            "temp_width": self.temp_line.get_linewidth(),
            "disp_width": self.disp_line.get_linewidth(),
            "background_color": self.figure.get_facecolor(),
            "xlabel": self.ax1.get_xlabel(),
            "ylabel1": self.ax1.get_ylabel(),
            "ylabel2": self.ax2.get_ylabel(),
        }
        try:
            with open(dosya_yolu, "w") as f:
                json.dump(theme, f)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Temayı kaydetme başarısız: {str(e)}")

    def load_theme(self):
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        dosya_yolu, _ = QFileDialog.getOpenFileName(self, "Tema Yükle", "", "JSON Dosyası (*.json)")
        if not dosya_yolu:
            return
        try:
            with open(dosya_yolu, "r") as f:
                theme = json.load(f)
            self.temp_line.set_color(theme.get("temp_color", "blue"))
            self.disp_line.set_color(theme.get("disp_color", "red"))
            self.temp_line.set_linewidth(theme.get("temp_width", 3.5))
            self.disp_line.set_linewidth(theme.get("disp_width", 3.5))
            # Ekstra ayarlar
            self.figure.patch.set_facecolor(theme.get("background_color", "white"))
            self.ax1.set_facecolor(theme.get("background_color", "white"))
            self.ax2.set_facecolor(theme.get("background_color", "white"))
            self.ax1.set_xlabel(theme.get("xlabel", "Sintering Time (seconds)"))
            self.ax1.set_ylabel(theme.get("ylabel1", "Temperature (°C)"))
            self.ax2.set_ylabel(theme.get("ylabel2", "Displacement (mm)"))
            self.canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tema yüklenemedi: {str(e)}")

    def set_axis_limits(self, ax, axis='x'):
        min_val, ok1 = QInputDialog.getDouble(self, f"{axis.upper()} Ekseni Minimum", "Minimum değeri girin:")
        if not ok1:
            return
        max_val, ok2 = QInputDialog.getDouble(self, f"{axis.upper()} Ekseni Maksimum", "Maksimum değeri girin:")
        if not ok2:
            return
        if axis == 'x':
            ax.set_xlim(min_val, max_val)
        elif axis == 'y':
            ax.set_ylim(min_val, max_val)
        self.canvas.draw()
    # --- Utility: Renk seçimi (RGB veya manuel hex input) ---
    def get_color_input(self, title="Renk Seç", default="#000000"):
        color = QColorDialog.getColor()
        if color.isValid():
            return color.name()
        text, ok = QInputDialog.getText(self, title, "Renk kodu girin (örnek: #FF0000):", text=default)
        if ok and text.startswith("#") and len(text) in [7, 9]:
            return text
        return None

    # --- Çizgi kalınlığı ayarlama ---
    def set_line_width(self, line):
        width, ok = QInputDialog.getDouble(self, "Çizgi Kalınlığı", "Kalınlık girin (örn. 1.0):", value=line.get_linewidth(), min=0.1, max=10.0, decimals=1)
        if ok:
            line.set_linewidth(width)
            self.canvas.draw()
            self.update_legend()

    # --- Eksen başlık rengi ayarlama ---
    def set_axis_label_color(self, ax, axis="x"):
        color = self.get_color_input("Başlık Rengi Seç", default="#000000")
        if color:
            if axis == "x":
                ax.xaxis.label.set_color(color)
            elif axis == "y":
                ax.yaxis.label.set_color(color)
            self.canvas.draw()

    # --- Tick rengi ayarlama ---
    def set_tick_color(self, ax, axis="x"):
        color = self.get_color_input("Tick Rengi Seç", default="#000000")
        if color:
            ax.tick_params(axis=axis, colors=color)
            self.canvas.draw()

    # --- Spine (eksen çizgisi) rengi ve kalınlığı ayarlama ---
    def set_spine_color(self, ax, which="bottom"):
        color = self.get_color_input("Spine Rengi Seç", default="#000000")
        if not color:
            return
        linewidth, ok = QInputDialog.getDouble(self, "Spine Kalınlığı", "Kalınlık girin (örn. 1.0):", value=ax.spines[which].get_linewidth(), min=0.1, max=10.0, decimals=1)
        if ok:
            ax.spines[which].set_color(color)
            ax.spines[which].set_linewidth(linewidth)
            self.canvas.draw()

    # --- Genel plot (aksın dış kenarları/border) spine rengi ayarlama ---
    def set_figure_border_color(self):
        color = self.get_color_input("Plot Kenarlık Rengi Seç", default="#000000")
        if not color:
            return
        # Tüm spine'lara uygula (ax1 ve ax2'nin ana spine'ları)
        for spine in self.ax1.spines.values():
            spine.set_color(color)
        for spine in self.ax2.spines.values():
            spine.set_color(color)
        self.canvas.draw()

    def set_figure_border_width(self):
        linewidth, ok = QInputDialog.getDouble(self, "Plot Kenarlık Kalınlığı", "Kalınlık girin (örn. 1.0):", value=self.ax1.spines["bottom"].get_linewidth(), min=0.1, max=10.0, decimals=1)
        if ok:
            for spine in self.ax1.spines.values():
                spine.set_linewidth(linewidth)
            for spine in self.ax2.spines.values():
                spine.set_linewidth(linewidth)
            self.canvas.draw()

    def __init__(self):
        self.y2_tick_format = '%.3f'
        self.legend1 = None
        self.legend2 = None
        self.legend_location = 'upper right'
        super().__init__()

        # --- Menu Bar Integration ---
        self.menu_bar = self.menuBar()
        self.menu_bar.setNativeMenuBar(False)
        # File menu
        file_menu = self.menu_bar.addMenu("Dosya")
        file_menu.addAction("Yeni XRD Yükle", self.load_additional_xrd)
        file_menu.addAction("Kaydet", self.save_plot)
        file_menu.addAction("Ayarları Kaydet", self.save_xrd_settings)
        file_menu.addAction("Ayarları Yükle", self.load_xrd_settings)
        file_menu.addAction("Projeyi Kaydet", self.save_project)
        file_menu.addAction("Projeyi Aç", self.load_project)
        file_menu.addSeparator()
        file_menu.addAction("Çıkış", self.close)
        # View menu
        view_menu = self.menu_bar.addMenu("Görünüm")
        view_menu.addAction("Tepe Noktalarını Göster", self.show_peaks)
        view_menu.addAction("Veri Tablosu (Tüm XRD)", self.open_xrd_data_table_entry)
        # Grafik menu (from Seebeck)
        grafik_menu = self.menu_bar.addMenu("Grafik")
        grafik_menu.addAction("Başlık Ekle", self.add_title)
        grafik_menu.addAction("X Eksen Etiketi", self.add_xlabel)
        grafik_menu.addAction("Y Eksen Etiketi", self.add_ylabel)
        grafik_menu.addSeparator()
        grafik_menu.addSeparator()
        grafik_menu.addAction("Çerçeve Rengini Seç", self.set_spine_color_menu)
        # --- Advanced graph customization options ---
        grafik_menu.addSeparator()
        grafik_menu.addAction("Grid Çizgilerini Göster/Gizle", self.toggle_grid)
        grafik_menu.addAction("X Eksen Aralığı Ayarla", self.set_xlim)
        grafik_menu.addAction("Y Eksen Aralığı Ayarla", self.set_ylim)
        grafik_menu.addSeparator()
        grafik_menu.addAction("Matplotlib Temasını Değiştir", self.change_theme)
        grafik_menu.addAction("Yayın Stili (Klasik)", self.apply_publication_theme)
        grafik_menu.addAction("Tema Kaydet (XRD)", self.save_xrd_theme)
        grafik_menu.addAction("Tema Yükle (XRD)", self.load_xrd_theme)
        # --- Extended: advanced label and visual settings ---
        grafik_menu.addSeparator()
        grafik_menu.addAction("Eksen Yazı Tipi Ayarları", self.set_axis_font_style)
        grafik_menu.addAction("Başlık Hizalamasını Ayarla", self.set_title_alignment)
        grafik_menu.addAction("Arka Plan Rengini Seç", self.set_background_color)
        grafik_menu.addAction("Otomatik Zoom/Pan Sıfırla", self.reset_zoom)
        # Legend submenu (clean and focused)
        legend_menu = grafik_menu.addMenu("Legend")
        legend_menu.addAction("Göster/Gizle", self.toggle_legend)
        legend_menu.addAction("Konum", self.legend_location_select)
        legend_menu.addAction("Yazı Tipi", self.legend_font_select)
        legend_menu.addAction("Yazı Rengi", self.legend_color_select)
        legend_menu.addAction("Çerçeve Aç/Kapat", self.toggle_legend_frame)
        legend_menu.addAction("Arka Plan Rengi", self.legend_background_color)
        legend_menu.addAction("Saydamlık (alpha)", self.legend_set_alpha)
        # --- Yeni üst menüler ---
        # Legends
        legends_menu = self.menu_bar.addMenu("Legends")
        legends_menu.addAction("Göster/Gizle", self.toggle_legend)
        legends_menu.addAction("Konumu Koordinat ile Ayarla", self.legend_position_by_coords)
        legends_menu.addAction("Göstergelerin Kalınlığını Ayarla", self.legend_handle_linewidth)
        legends_menu.addAction("Göstergelerin Rengini Ayarla", self.legend_handle_color)
        legends_menu.addAction("Göstergelerin Büyüklüğünü Ayarla (marker)", self.legend_handle_markersize)
        legends_menu.addSeparator()
        legends_menu.addAction("Yazı Tipi / Boyutu", self.legend_font_select)
        legends_menu.addAction("Yazı Rengi", self.legend_color_select)
        legends_menu.addAction("Yazı Kalınlığı (Normal/Kalın)", self.legend_text_weight)
        legends_menu.addSeparator()
        legends_menu.addAction("Sıralamayı Düzenle", self.legend_reorder_dialog)

        # Eksenler
        eksenler_menu = self.menu_bar.addMenu("Eksenler")
        eksenler_menu.addAction("X Eksen İsmini Ayarla", lambda: self.axis_set_label('x'))
        eksenler_menu.addAction("Y Eksen İsmini Ayarla", lambda: self.axis_set_label('y'))
        eksenler_menu.addAction("X Eksen Yazı Tipi/Boyutu", lambda: self.axis_set_label_font('x'))
        eksenler_menu.addAction("Y Eksen Yazı Tipi/Boyutu", lambda: self.axis_set_label_font('y'))
        eksenler_menu.addAction("X Eksen Rengi", lambda: self.set_axis_label_color(self.ax, 'x'))
        eksenler_menu.addAction("Y Eksen Rengi", lambda: self.set_axis_label_color(self.ax, 'y'))
        eksenler_menu.addAction("X Etiket Konumu (coords)", lambda: self.axis_set_label_pos('x'))
        eksenler_menu.addAction("Y Etiket Konumu (coords)", lambda: self.axis_set_label_pos('y'))
        eksenler_menu.addAction("X Eksen Çizgi Kalınlığı", lambda: self.axis_spine_width('x'))
        eksenler_menu.addAction("Y Eksen Çizgi Kalınlığı", lambda: self.axis_spine_width('y'))

        # Eksen Çizgileri (ticks)
        tick_menu = self.menu_bar.addMenu("Eksen Çizgileri")
        tick_menu.addAction("X Major/Minor Aralıklarını Ayarla", lambda: self.axis_set_tick_locator('x'))
        tick_menu.addAction("Y Major/Minor Aralıklarını Ayarla", lambda: self.axis_set_tick_locator('y'))
        tick_menu.addAction("X Tick Çizgi Kalınlığı/Rengi", lambda: self.axis_tick_style('x'))
        tick_menu.addAction("Y Tick Çizgi Kalınlığı/Rengi", lambda: self.axis_tick_style('y'))
        tick_menu.addAction("X Tick Yazı Tipi/Rengi", lambda: self.axis_tick_label_font('x'))
        tick_menu.addAction("Y Tick Yazı Tipi/Rengi", lambda: self.axis_tick_label_font('y'))
        tick_menu.addSeparator()
        tick_menu.addAction("X Min/Max Ayarla", lambda: self.set_axis_limits(self.ax, 'x'))
        tick_menu.addAction("Y Min/Max Ayarla", lambda: self.set_axis_limits(self.ax, 'y'))

        # Çizgi Çekme
        lines_menu = self.menu_bar.addMenu("Çizgi Çekme")
        lines_menu.addAction("Grid Aç/Kapat", self.toggle_grid)
        lines_menu.addAction("Dikey Çizgi(ler) Ekle", self.add_vertical_lines)
        lines_menu.addAction("Dikey Çizgileri Temizle", self.clear_vertical_lines)

        # Ön İşleme menüsü: smoothing ve arka plan çıkarma
        preprocess_menu = self.menu_bar.addMenu("Ön İşleme")
        preprocess_menu.addAction("Yumuşat (Savitzky–Golay)", self.preprocess_savgol)
        preprocess_menu.addAction("Arka Plan Çıkar (ALS)", self.preprocess_baseline_als)
        preprocess_menu.addAction("Arka Plan Çıkar (Rolling Min)", self.preprocess_baseline_rolling)
        preprocess_menu.addAction("Arka Planı Göster/Gizle", self.toggle_background_curve)
        preprocess_menu.addSeparator()
        preprocess_menu.addAction("Orijinale Dön", self.preprocess_reset)
        # --- Startup: initialize without prompting for style or file ---
        # Prepare core state and UI pieces; user can choose theme or load files later from menus
        self.xrd_datasets = []
        self.df = None
        self.control_rows = []
        # Load PDF database if available
        try:
            with open("pdf_cards.json", "r") as f:
                self.pdf_db = json.load(f)
        except FileNotFoundError:
            self.pdf_db = {}

        # Basic inputs (defaults); user can change via UI later
        self.add_xrd_button = QPushButton("Veri Ekle")
        self.xlabel_input = QLineEdit("2θ (°)")
        self.ylabel_input = QLineEdit("Intensity (a.u.)")
        # Only matplotlib-compatible fonts (DejaVu and some common ones)
        self.fonts = ["DejaVu Sans", "DejaVu Serif", "Arial", "Times New Roman", "Courier New", "Helvetica"]
        self.font_combo = QComboBox()
        self.font_combo.addItems(self.fonts)
        self.font_combo.setCurrentText("DejaVu Sans")
        self.font_size_input = QLineEdit("12")
        self.apply_style_button = QPushButton("Stili Uygula")
        self.add_xrd_button.clicked.connect(self.open_manual_data_dialog)
        self.apply_style_button.clicked.connect(self.update_plot_style)

        # Color per line store
        self.line_colors = {}

        # Draw an empty plot area; datasets can be added later
        self.plot_graph()
    # --- Advanced graph customization methods for Grafik menu ---
    # (removed duplicate early toggle_grid method)

    def set_xlim(self):
        min_val, ok1 = QInputDialog.getDouble(self, "X Min", "Alt sınır:", 0, -1e6, 1e6, 2)
        if not ok1:
            return
        max_val, ok2 = QInputDialog.getDouble(self, "X Max", "Üst sınır:", 0, -1e6, 1e6, 2)
        if not ok2:
            return
        self.ax.set_xlim(min_val, max_val)
        self.canvas.draw()

    def set_ylim(self):
        min_val, ok1 = QInputDialog.getDouble(self, "Y Min", "Alt sınır:", 0, -1e6, 1e6, 2)
        if not ok1:
            return
        max_val, ok2 = QInputDialog.getDouble(self, "Y Max", "Üst sınır:", 0, -1e6, 1e6, 2)
        if not ok2:
            return
        self.ax.set_ylim(min_val, max_val)
        self.canvas.draw()

    def change_theme(self):
        themes = sorted(plt.style.available)
        theme, ok = QInputDialog.getItem(self, "Tema Seç", "Matplotlib Teması:", themes, editable=False)
        if ok:
            plt.style.use(theme)
            # Re-apply UI-selected font so the theme doesn't override it
            try:
                fname = self.font_combo.currentText()
                fsize = int(self.font_size_input.text())
            except Exception:
                fname, fsize = "DejaVu Sans", 12
            self.apply_font_settings(fname, fsize)
            if hasattr(self, 'canvas'):
                self.canvas.draw()
        return

    def apply_publication_theme(self):
        """
        Tek tıkla makale (publication) tarzı sade stil uygular:
        - Beyaz zemin
        - Dört kenarda siyah çerçeve
        - İçeri bakan major/minor tikler; üst ve sağ tikler açık
        - Grid kapalı
        """
        try:
            plt.style.use('default')
            if hasattr(self, "theme_combo"):
                self.theme_combo.setCurrentText('default')
        except Exception:
            pass

        if hasattr(self, "figure") and self.figure is not None:
            self.figure.patch.set_facecolor('white')

        if not hasattr(self, "ax") or self.ax is None:
            return

        ax = self.ax
        # Arkaplan
        ax.set_facecolor('white')
        # Dört spine görünür ve siyah
        for side in ['bottom', 'top', 'left', 'right']:
            ax.spines[side].set_visible(True)
            ax.spines[side].set_color('black')
            ax.spines[side].set_linewidth(1.0)
        # Tick ayarları
        ax.minorticks_on()
        ax.tick_params(axis='both', which='both', direction='in', colors='black', top=True, right=True, width=1)
        ax.tick_params(which='major', length=6)
        ax.tick_params(which='minor', length=3)
        # Grid kapalı
        ax.grid(False)
        # Eksen yazıları siyah
        ax.xaxis.label.set_color('black')
        ax.yaxis.label.set_color('black')
        if hasattr(self, "canvas"):
            self.canvas.draw()

    def save_xrd_theme(self):
        """Mevcut görünümü tema gibi JSON'a kaydeder (Ayarları Kaydet ile aynı içerik)."""
        # Yeniden kullan: save_xrd_settings zaten gerekli görsel ayarları yazıyor
        return self.save_xrd_settings()

    def load_xrd_theme(self):
        """JSON'dan görünümü geri yükler (Ayarları Yükle ile aynı içerik)."""
        return self.load_xrd_settings()

    # --- Replacement: plot_graph for XRD pattern ---
    def plot_graph(self):
        # Create Figure and Axes
        self.figure, self.ax = plt.subplots()

        # If we have registered datasets, draw them all; otherwise fall back to self.df
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            for d in self.xrd_datasets:
                df = d["df"]
                x = df.iloc[:, 0].values
                y = df.iloc[:, 1].values + d.get("offset", 0.0)
                self.ax.plot(x, y, label=d.get("filename", "XRD"), color=d.get("color", "#1f77b4"))
        elif hasattr(self, "df") and self.df is not None:
            x = self.df.iloc[:, 0].values
            y = self.df.iloc[:, 1].values
            self.ax.plot(x, y, label=getattr(self, "main_filename", "XRD"), color="#1f77b4")
        # else: start with an empty axes; user can add datasets later from the UI

        # Use explicit label/title with UI-selected font, not Big Caslon (avoids missing glyphs)
        self.ax.set_title("XRD Pattern")
        self.ax.set_xlabel("2θ (°)")
        self.ax.set_ylabel("Intensity (a.u.)")
        # Apply current UI font choice to avoid theme default & missing glyphs
        try:
            fname = self.font_combo.currentText() if hasattr(self, 'font_combo') else "DejaVu Sans"
            fsize = int(self.font_size_input.text()) if hasattr(self, 'font_size_input') and self.font_size_input.text() else 12
        except Exception:
            fname, fsize = "DejaVu Sans", 12
        self.apply_font_settings(fname, fsize)
        # Filter legend so only valid labels are shown
        handles, labels = self.ax.get_legend_handles_labels()
        handles = [h for h, l in zip(handles, labels) if l and not l.startswith("_")]
        labels  = [l for l in labels if l and not l.startswith("_")]
        if handles:
            self.ax.legend(handles, labels)

        # Embed canvas into GUI layout
        self.canvas = FigureCanvas(self.figure)

        # --- Restore all previously used controls ---
        # Color picker for line color
        self.color_button = QPushButton("Color")
        self.color_button.clicked.connect(self.select_line_color)

        # Offset input
        self.offset_input = QLineEdit("0.0")
        self.offset_input.setFixedWidth(60)
        self.offset_input.setToolTip("Offset (y-shift) for stacking multiple patterns")

        # 2θ filtering controls
        self.theta_min = QLineEdit()
        self.theta_min.setPlaceholderText("Min 2θ")
        self.theta_min.setFixedWidth(60)
        self.theta_max = QLineEdit()
        self.theta_max.setPlaceholderText("Max 2θ")
        self.theta_max.setFixedWidth(60)
        self.theta_filter_btn = QPushButton("Apply 2θ Filter")
        self.theta_filter_btn.clicked.connect(self.apply_theta_filter)

        # Peak toggle
        self.peak_toggle = QCheckBox("Show Peaks")
        self.peak_toggle.setChecked(False)
        self.peak_toggle.stateChanged.connect(self.update_graph_from_df)

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_plot)

        # Export peaks button
        self.export_peaks_btn = QPushButton("Export Peaks")
        self.export_peaks_btn.clicked.connect(self.export_peaks)

        # Main layout and control layout
        main_layout = QVBoxLayout()

        # --- New XRD control layout at the top ---
        xrd_control_layout = QHBoxLayout()
        xrd_control_layout.addWidget(QLabel("Yeni XRD (manuel):"))
        xrd_control_layout.addWidget(self.add_xrd_button)
        xrd_control_layout.addWidget(QLabel("X Etiketi:"))
        xrd_control_layout.addWidget(self.xlabel_input)
        xrd_control_layout.addWidget(QLabel("Y Etiketi:"))
        xrd_control_layout.addWidget(self.ylabel_input)
        xrd_control_layout.addWidget(QLabel("Font:"))
        xrd_control_layout.addWidget(self.font_combo)
        xrd_control_layout.addWidget(QLabel("Boyut:"))
        xrd_control_layout.addWidget(self.font_size_input)
        xrd_control_layout.addWidget(self.apply_style_button)
        # Tema seçici
        xrd_control_layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(sorted(plt.style.available))
        xrd_control_layout.addWidget(self.theme_combo)
        self.theme_apply_btn = QPushButton("Uygula")
        self.theme_apply_btn.clicked.connect(self.apply_theme_from_combo)
        xrd_control_layout.addWidget(self.theme_apply_btn)
        main_layout.addLayout(xrd_control_layout)

        control_layout = QHBoxLayout()
        # Add controls to control_layout
        control_layout.addWidget(QLabel("Color:"))
        control_layout.addWidget(self.color_button)
        control_layout.addSpacing(10)
        control_layout.addWidget(QLabel("Offset:"))
        control_layout.addWidget(self.offset_input)
        control_layout.addSpacing(10)
        control_layout.addWidget(QLabel("2θ Range:"))
        control_layout.addWidget(self.theta_min)
        control_layout.addWidget(self.theta_max)
        control_layout.addWidget(self.theta_filter_btn)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.peak_toggle)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(self.export_peaks_btn)
        control_layout.addStretch()

        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.canvas)

        # --- Add XRD dataset controls panel (scrollable) ---
        # (all required PyQt5.QtWidgets imports are already at the top)
        # Only initialize layouts/scroll area once; don't re-add on every call
        if not hasattr(self, "control_panel_layout"):
            self.control_panel_layout = QVBoxLayout()
            self.control_panel_layout.setSpacing(2)
            control_panel_widget = QWidget()
            control_panel_widget.setLayout(self.control_panel_layout)
            self.control_scroll_area = QScrollArea()
            self.control_scroll_area.setWidgetResizable(True)
            self.control_scroll_area.setWidget(control_panel_widget)
            main_layout.addWidget(QLabel("XRD Dataset Controls:"))
            main_layout.addWidget(self.control_scroll_area)
            # Populate control rows for all current datasets (including the main one)
            if not hasattr(self, "control_rows"):
                self.control_rows = []
            existing_names = {row["filename"] for row in self.control_rows} if self.control_rows else set()
            if hasattr(self, "xrd_datasets"):
                for d in self.xrd_datasets:
                    if d["filename"] not in existing_names:
                        self.add_control_row(d["filename"], d.get("offset", 0.0), d.get("color", "#1f77b4"))
        # Ensure control_rows always exists
        if not hasattr(self, "control_rows"):
            self.control_rows = []

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Status bar: canlı koordinatlar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_label = QLabel("x: -, y: -")
        self.status.addPermanentWidget(self.status_label)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        self.canvas.draw()

    def load_additional_xrd(self):
        import os
        file_path, _ = QFileDialog.getOpenFileName(self, "Yeni XRD Dosyası", "", "Text Files (*.txt)")
        if file_path:
            try:
                df = pd.read_csv(file_path, sep="\t", header=None)
                x = df.iloc[:, 0].values
                y = df.iloc[:, 1].values
                # Offset input
                offset, _ = QInputDialog.getDouble(self, "Y Ofset Gir", f"{os.path.basename(file_path)} için ofset:", 0.0, -10000, 10000, 2)
                color = QColorDialog.getColor().name()
                y_plot = y + offset
                self.ax.plot(x, y_plot, label=os.path.basename(file_path), color=color)
                self.ax.legend()
                self.canvas.draw()
                # Store dataset info
                self.xrd_datasets.append({
                    "filename": os.path.basename(file_path),
                    "df": df,
                    "offset": offset,
                    "color": color
                })
                # Add control row for this dataset
                self.add_control_row(os.path.basename(file_path), offset, color)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya yüklenirken hata oluştu:\n{str(e)}")

    def add_control_row(self, filename, offset, color):
        # Do not clear or reset layout; just add new row
        row_layout = QHBoxLayout()
        label = QLabel(filename)
        spin = QDoubleSpinBox()
        spin.setRange(-10000, 10000)
        spin.setDecimals(2)
        spin.setValue(offset)
        color_btn = QPushButton()
        color_btn.setStyleSheet(f"background-color: {color}")
        update_btn = QPushButton("Güncelle")
        # Find dataset index
        idx = None
        for i, d in enumerate(self.xrd_datasets):
            if d["filename"] == filename:
                idx = i
                break
        def choose_color():
            c = QColorDialog.getColor()
            if c.isValid():
                color_btn.setStyleSheet(f"background-color: {c.name()}")
                self.xrd_datasets[idx]["color"] = c.name()
        color_btn.clicked.connect(choose_color)
        def update_row():
            self.xrd_datasets[idx]["offset"] = spin.value()
            # Update color in case changed (already set in choose_color)
            self.redraw_plot()
        update_btn.clicked.connect(update_row)
        row_layout.addWidget(label)
        row_layout.addWidget(QLabel("Offset:"))
        row_layout.addWidget(spin)
        row_layout.addWidget(QLabel("Renk:"))
        row_layout.addWidget(color_btn)
        row_layout.addWidget(update_btn)
        row_layout.addStretch()
        self.control_panel_layout.addLayout(row_layout)
        # Store row widgets for future reference if needed
        if not hasattr(self, "control_rows"):
            self.control_rows = []
        self.control_rows.append({
            "filename": filename,
            "layout": row_layout,
            "label": label,
            "spin": spin,
            "color_btn": color_btn,
            "update_btn": update_btn
        })

    def redraw_plot(self):
        # Safety guard: if axes/canvas are not yet created (e.g., called before plot_graph), do nothing.
        if not hasattr(self, "ax") or not hasattr(self, "canvas"):
            return
        # remember current labels/title to preserve after clear
        current_xlabel = self.ax.get_xlabel() if hasattr(self, "ax") else "2θ (°)"
        current_ylabel = self.ax.get_ylabel() if hasattr(self, "ax") else "Intensity (a.u.)"
        current_title  = self.ax.get_title()  if hasattr(self, "ax") else "XRD Pattern"
        current_xlim = self.ax.get_xlim() if hasattr(self, "ax") else None
        current_ylim = self.ax.get_ylim() if hasattr(self, "ax") else None
        self.ax.clear()
        # Plot all datasets in self.xrd_datasets
        for d in self.xrd_datasets:
            df = d["df"]
            x = df.iloc[:, 0].values
            y = df.iloc[:, 1].values + d["offset"]
            self.ax.plot(x, y, label=d["filename"], color=d["color"])
        # Use inputs if present (kept in sync with axes), otherwise preserve previous values
        xlabel = self.xlabel_input.text() if hasattr(self, "xlabel_input") else current_xlabel
        ylabel = self.ylabel_input.text() if hasattr(self, "ylabel_input") else current_ylabel
        # Set labels and title without forcing big_caslon_font
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(current_title)
        try:
            font_name = self.font_combo.currentText()
            font_size = int(self.font_size_input.text())
        except Exception:
            font_name = "DejaVu Sans"
            font_size = 12
        self.apply_font_settings(font_name, font_size)
        # Restore axis limits if possible
        if current_xlim is not None:
            self.ax.set_xlim(current_xlim)
        if current_ylim is not None:
            self.ax.set_ylim(current_ylim)
        # Filter legend so only valid labels are shown
        handles, labels = self.ax.get_legend_handles_labels()
        handles = [h for h, l in zip(handles, labels) if l and not l.startswith("_")]
        labels  = [l for l in labels if l and not l.startswith("_")]
        if handles:
            self.ax.legend(handles, labels)
        self.canvas.draw()
    def show_peaks(self):
        if not hasattr(self, "df") or self.df is None or self.df.empty:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce geçerli bir XRD verisi yükleyin.")
            return
        # (rest of show_peaks logic if any)

    def update_plot_style(self):
        xlabel = self.xlabel_input.text()
        ylabel = self.ylabel_input.text()
        current_title = self.ax.get_title() if hasattr(self, 'ax') else "XRD Pattern"
        # Set labels and title without forcing big_caslon_font
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(current_title)
        # Apply chosen font settings
        try:
            font_name = self.font_combo.currentText()
            font_size = int(self.font_size_input.text())
        except Exception:
            font_name = "DejaVu Sans"
            font_size = 12
        self.apply_font_settings(font_name, font_size)
        if hasattr(self, 'canvas'):
            self.canvas.draw()

    def select_line_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Set color for the main XRD line
            for line in self.ax.get_lines():
                line.set_color(color.name())
            self.canvas.draw()
    # --- Helper: Save current plot (XRD-style) ---
    def save_plot(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Grafiği Kaydet", "", "SVG Files (*.svg);;PNG Files (*.png);;PDF Files (*.pdf)")
        if file_path:
            self.figure.savefig(file_path, dpi=600, bbox_inches='tight')

    # --- Helper: Clear current plot (XRD-style) ---
    def clear_plot(self):
        # Safely clear current plot(s) without rebuilding any tabs/panels
        if hasattr(self, 'ax') and self.ax is not None:
            self.ax.clear()
        if hasattr(self, 'ax1') and self.ax1 is not None:
            self.ax1.clear()
        if hasattr(self, 'ax2') and self.ax2 is not None:
            self.ax2.clear()
            self.ax2 = None
        if hasattr(self, 'xrd_datasets') and isinstance(self.xrd_datasets, list):
            self.xrd_datasets.clear()
        if hasattr(self, 'xrd_files'):
            self.xrd_files.clear()
        if hasattr(self, 'canvas') and self.canvas is not None:
            self.canvas.draw()

    def renk_sec_temp(self):
        renk = QColorDialog.getColor()
        if renk.isValid():
            renk_hex = renk.name()
            self.temp_line.set_color(renk_hex)
            self.ax1.yaxis.label.set_color(renk_hex)
            self.ax1.tick_params(axis='y', colors=renk_hex)
            self.canvas.draw()
            self.update_legend()

    def renk_sec_disp(self):
        renk = QColorDialog.getColor()
        if renk.isValid():
            renk_hex = renk.name()
            self.disp_line.set_color(renk_hex)
            self.ax2.yaxis.label.set_color(renk_hex)
            self.ax2.tick_params(axis='y', colors=renk_hex)
            self.canvas.draw()
            self.update_legend()

    def apply_font_to_labels(self, labels, font):
        for label in labels:
            label.set_fontsize(font.pointSize())
            label.set_fontname(font.family())
            label.set_fontweight(font.weight())

    def font_sec_temp(self):
        font, ok = QFontDialog.getFont()
        if ok:
            # Only change Y1 axis label (left side)
            self.ax1.set_ylabel('Temperature (°C)', fontsize=font.pointSize(), fontname=font.family(), fontweight=font.weight(), color=self.temp_line.get_color())
            self.canvas.draw()

    def font_sec_disp(self):
        font, ok = QFontDialog.getFont()
        if ok:
            # Only change Y2 axis label (right side)
            self.ax2.set_ylabel('Displacement (mm)', fontsize=font.pointSize(), fontname=font.family(), fontweight=font.weight(), color=self.disp_line.get_color())
            self.canvas.draw()

    def font_sec_xticks(self):
        font, ok = QFontDialog.getFont()
        if ok:
            # Only affect X axis tick labels
            self.apply_font_to_labels(self.ax1.get_xticklabels(), font)
            self.canvas.draw()

    def font_sec_yticks(self):
        font, ok = QFontDialog.getFont()
        if ok:
            # Only affect Y1 and Y2 tick labels
            self.apply_font_to_labels(self.ax1.get_yticklabels() + self.ax2.get_yticklabels(), font)
            self.canvas.draw()

    def font_sec_axes(self):
        font, ok = QFontDialog.getFont()
        if ok:
            # Only affect X axis label
            self.ax1.set_xlabel(self.ax1.get_xlabel(), fontsize=font.pointSize(), fontname=font.family(), fontweight=font.weight())
            self.canvas.draw()

    def grafik_kaydet(self):

        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self,
            "Grafiği Kaydet",
            "",
            "PNG Dosyası (*.png);;PDF Dosyası (*.pdf);;SVG Dosyası (*.svg)"
        )
        if not dosya_yolu:
            return

        # DPI seçimi
        dpi, ok_dpi = QInputDialog.getInt(self, "DPI Seçimi", "DPI değeri girin:", 300, 72, 1200)
        if not ok_dpi:
            return

        # Boyut seçenekleri (inç cinsinden)
        boyutlar_inch = {
            "4:3 (8in x 6in)": (8, 6),
            "4:3 (6in x 4.5in)": (6, 4.5),
            "16:9 (6.4in x 3.6in)": (6.4, 3.6),
            "16:9 (10in x 5.625in)": (10, 5.625),
            "A4 (8.27in x 11.69in)": (8.27, 11.69),
        }

        secenekler = list(boyutlar_inch.keys())
        boyut_adi, ok_size = QInputDialog.getItem(self, "Görsel Boyutu (inch)", "Boyut seçin:", secenekler, 0, False)
        if not ok_size:
            return

        width_inch, height_inch = boyutlar_inch[boyut_adi]
        self.figure.set_size_inches(width_inch, height_inch)

        self.figure.savefig(dosya_yolu, dpi=dpi, bbox_inches='tight')
        QMessageBox.information(self, "Kaydedildi", f"Görsel başarıyla kaydedildi:\n{dosya_yolu}")

    def line_style_sec(self):
        stil, ok = QInputDialog.getText(self, "Çizgi Stili", "Stil girin (örneğin: '-', '--', '-.', ':'):")
        if ok:
            if stil in ['-', '--', '-.', ':']:
                self.temp_line.set_linestyle(stil)
                self.disp_line.set_linestyle(stil)
                self.canvas.draw()
                self.update_legend()
            else:
                QMessageBox.warning(self, "Geçersiz Stil", "Lütfen '-', '--', '-.', ':' gibi geçerli bir stil girin.")

    def set_background_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            renk_hex = color.name()
            # Apply background to the current XRD axis and the whole figure
            if hasattr(self, 'ax') and self.ax is not None:
                self.ax.set_facecolor(renk_hex)
            if hasattr(self, 'figure') and self.figure is not None:
                self.figure.patch.set_facecolor(renk_hex)
            # If dual axes exist in other modes, try to color them as well (safe checks)
            if hasattr(self, 'ax1') and self.ax1 is not None:
                self.ax1.set_facecolor(renk_hex)
            if hasattr(self, 'ax2') and self.ax2 is not None:
                self.ax2.set_facecolor(renk_hex)
            self.canvas.draw()

    def toggle_grid(self):
        # Use a dedicated state attribute for XRD grid and toggle it safely
        current_state = getattr(self, "_xrd_grid_state", False)
        new_state = not current_state
        if hasattr(self, 'ax') and self.ax is not None:
            self.ax.grid(new_state)
        # Also try to toggle for ax1/ax2 if they exist (other modes)
        if hasattr(self, 'ax1') and self.ax1 is not None:
            self.ax1.grid(new_state)
        if hasattr(self, 'ax2') and self.ax2 is not None:
            self.ax2.grid(new_state)
        self._xrd_grid_state = new_state
        self.canvas.draw()

    def reset_zoom(self):
        """Reset zoom/pan for the active XRD axis and redraw."""
        if hasattr(self, 'ax') and self.ax is not None:
            # Reset view limits to data
            self.ax.relim()
            self.ax.autoscale()
        if hasattr(self, 'figure') and self.figure is not None:
            self.figure.canvas.draw_idle()
        else:
            self.canvas.draw()

    def set_spine_color_menu(self):
        """Menu-safe spine color setter for the active XRD axis (no args)."""
        color = self.get_color_input("Spine Rengi Seç", default="#000000")
        if not color:
            return
        if hasattr(self, 'ax') and self.ax is not None:
            for spine in self.ax.spines.values():
                spine.set_edgecolor(color)
            self.canvas.draw()

    def add_title(self):
        title, ok = QInputDialog.getText(self, "Grafik Başlığı", "Başlık girin:")
        if ok:
            self.ax.set_title(title)
            self.canvas.draw()

    def add_xlabel(self):
        text, ok = QInputDialog.getText(self, "X Eksen Etiketi", "Etiket girin:")
        if ok:
            self.ax.set_xlabel(text)
            self.canvas.draw()

    def add_ylabel(self):
        text, ok = QInputDialog.getText(self, "Y Eksen Etiketi", "Etiket girin:")
        if ok:
            self.ax.set_ylabel(text)
            self.canvas.draw()

    def reset_view(self):
        self.ax1.clear()
        self.ax2.clear()

        self.temp_line, = self.ax1.plot(df['Time'], df['Temperature'], '-', color='blue', linewidth=3.5, label='Temperature')
        self.ax2 = self.ax1.twinx()
        # --- Y2 tick formatting and spacing ---
        self.ax2.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5))
        self.ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
        self.ax2.tick_params(labelsize=10)
        self.disp_line, = self.ax2.plot(df['Time'], df['Displacement'], '-', color='red', linewidth=3.5, label='Displacement')

        self.ax1.set_xlabel('Sintering Time (seconds)', fontsize=14, fontweight='bold', color='black')
        self.ax1.set_ylabel('Temperature (°C)', fontsize=14, fontweight='bold', color='blue')
        self.ax2.set_ylabel('Displacement (mm)', fontsize=14, fontweight='bold', color='red')
        self.ax1.tick_params(axis='both', labelsize=12, width=2)
        self.ax2.tick_params(axis='both', labelsize=12, width=2)

        self.canvas.draw()
        self.update_legend()

    def toggle_lines(self):
        self.temp_line.set_visible(not self.temp_line.get_visible())
        self.disp_line.set_visible(not self.disp_line.get_visible())
        self.canvas.draw()

    def toggle_legend(self):
        if self.legend1:
            self.legend1.set_visible(not self.legend1.get_visible())
        if self.legend2:
            self.legend2.set_visible(not self.legend2.get_visible())
        self.canvas.draw()

    def legend_font_select(self):
        font, ok = QFontDialog.getFont()
        if ok:
            self.update_legend_text_style(font=font)

    def legend_color_select(self):
        color = self.get_color_input("Legend Yazı Rengi Seç", default="#000000")
        if color:
            self.update_legend_text_style(color=color)

    def legend_location_select(self):
        locations = ['best', 'upper right', 'upper left', 'lower left', 'lower right',
                     'right', 'center left', 'center right', 'lower center',
                     'upper center', 'center']
        location, ok = QInputDialog.getItem(self, "Legend Konumu", "Konum Seçin:", locations, 0, False)
        if ok:
            self.legend_location = location
            self.update_legend()

    def toggle_legend_frame(self):
        for legend in [self.legend1, self.legend2]:
            if legend:
                frame = legend.get_frame()
                frame.set_visible(not frame.get_visible())
        self.canvas.draw()

    def legend_background_color(self):
        color = self.get_color_input("Legend Arka Plan Rengi Seç", default="#FFFFFF")
        if color:
            for legend in [self.legend1, self.legend2]:
                if legend:
                    legend.get_frame().set_facecolor(color)
            self.canvas.draw()

    def legend_set_alpha(self):
        alpha, ok = QInputDialog.getDouble(self, "Saydamlık", "0.0 - 1.0 arasında bir değer girin:", value=1.0, min=0.0, max=1.0, decimals=2)
        if ok:
            for legend in [self.legend1, self.legend2]:
                if legend:
                    legend.get_frame().set_alpha(alpha)
            self.canvas.draw()

    def update_legend(self):
        loc = getattr(self, 'legend_location', 'best')

        # collect handles/labels from current ax (single-axis XRD) or dual axes
        handles_all = []
        labels_all = []
        target_ax = None

        if hasattr(self, 'ax1') and self.ax1 is not None:
            h1, l1 = self.ax1.get_legend_handles_labels()
            handles_all += h1; labels_all += l1
            target_ax = self.ax1
        if hasattr(self, 'ax2') and self.ax2 is not None:
            h2, l2 = self.ax2.get_legend_handles_labels()
            handles_all += h2; labels_all += l2
            if target_ax is None:
                target_ax = self.ax2

        if hasattr(self, 'ax') and self.ax is not None:
            h, l = self.ax.get_legend_handles_labels()
            # filter out Matplotlib-internal labels
            fl = [(hh, ll) for hh, ll in zip(h, l) if ll and not ll.startswith('_')]
            if fl:
                hh, ll = zip(*fl)
                handles_all += list(hh); labels_all += list(ll)
            if target_ax is None:
                target_ax = self.ax

        if not handles_all or target_ax is None:
            self.legend1 = None; self.legend2 = None
            if hasattr(self, "canvas"): self.canvas.draw()
            return

        # apply custom order if provided
        order = getattr(self, "legend_custom_order", None)
        if order and isinstance(order, list):
            label_to_handle = {lbl: h for h, lbl in zip(handles_all, labels_all)}
            ordered_handles = [label_to_handle[lbl] for lbl in order if lbl in label_to_handle]
            ordered_labels  = [lbl for lbl in order if lbl in label_to_handle]
            # append any missing labels at the end
            for h, lbl in zip(handles_all, labels_all):
                if lbl not in ordered_labels:
                    ordered_handles.append(h)
                    ordered_labels.append(lbl)
            handles_all, labels_all = ordered_handles, ordered_labels

        leg = target_ax.legend(handles=handles_all, labels=labels_all, loc=loc, frameon=True)
        self.legend1 = leg
        self.legend2 = leg
        if hasattr(self, "canvas"):
            self.canvas.draw()

    def update_legend_text_style(self, font=None, color=None):
        for legend in [self.legend1, self.legend2]:
            if not legend:
                continue
            for text in legend.get_texts():
                if font:
                    text.set_fontsize(font.pointSize())
                    text.set_fontname(font.family())
                    text.set_fontweight(font.weight())
                if color:
                    text.set_color(color)
        self.canvas.draw()

    # --------- XRD Settings Save/Load ----------
    def _current_style_name(self):
        # best-effort: use theme_combo if present
        try:
            return self.theme_combo.currentText()
        except Exception:
            return None

    def save_xrd_settings(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Ayarları Kaydet", "", "JSON (*.json)")
        if not fname:
            return
        cfg = {}
        # global figure/axes
        cfg["style"] = self._current_style_name()
        if hasattr(self, "ax") and self.ax is not None:
            cfg["xlabel"] = self.ax.get_xlabel()
            cfg["ylabel"] = self.ax.get_ylabel()
            cfg["title"]  = self.ax.get_title()
            cfg["xlim"]   = list(self.ax.get_xlim())
            cfg["ylim"]   = list(self.ax.get_ylim())
            # Save font info for labels and title
            cfg["xlabel_font"] = {
                "name": self.ax.xaxis.label.get_fontname(),
                "size": self.ax.xaxis.label.get_size(),
                "weight": self.ax.xaxis.label.get_fontweight(),
                "style": self.ax.xaxis.label.get_fontstyle()
            }
            cfg["ylabel_font"] = {
                "name": self.ax.yaxis.label.get_fontname(),
                "size": self.ax.yaxis.label.get_size(),
                "weight": self.ax.yaxis.label.get_fontweight(),
                "style": self.ax.yaxis.label.get_fontstyle()
            }
            cfg["title_font"] = {
                "name": self.ax.title.get_fontname(),
                "size": self.ax.title.get_size(),
                "weight": self.ax.title.get_fontweight(),
                "style": self.ax.title.get_fontstyle()
            }
        # Save UI font controls explicitly as well
        try:
            cfg["ui_font"] = {
                "name": self.font_combo.currentText() if hasattr(self, 'font_combo') else None,
                "size": int(self.font_size_input.text()) if hasattr(self, 'font_size_input') and self.font_size_input.text() else None,
            }
        except Exception:
            cfg["ui_font"] = {"name": None, "size": None}
        cfg["grid"] = getattr(self, "_xrd_grid_state", False)
        # legend
        cfg["legend_location"] = getattr(self, "legend_location", "best")
        cfg["legend_custom_order"] = getattr(self, "legend_custom_order", None)
        # datasets (filename, color, offset)
        datasets = []
        if hasattr(self, "xrd_datasets"):
            for d in self.xrd_datasets:
                datasets.append({
                    "filename": d.get("filename"),
                    "color": d.get("color"),
                    "offset": d.get("offset", 0.0)
                })
        cfg["datasets"] = datasets
        # write
        try:
            with open(fname, "w") as f:
                json.dump(cfg, f, indent=2)
            QMessageBox.information(self, "Bilgi", "Ayarlar kaydedildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilemedi:\n{e}")

    def load_xrd_settings(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Ayarları Yükle", "", "JSON (*.json)")
        if not fname:
            return
        try:
            with open(fname, "r") as f:
                cfg = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayar dosyası açılamadı:\n{e}")
            return

        try:
            # style (ask the user before applying the saved Matplotlib theme)
            style = cfg.get("style")
            if style:
                try:
                    reply = QMessageBox.question(
                        self,
                        "Tema Uygulansın mı?",
                        f"Kaydedilen tema (style='{style}') uygulansın mı?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes,
                    )
                    if reply == QMessageBox.Yes:
                        plt.style.use(style)
                        if hasattr(self, "theme_combo"):
                            self.theme_combo.setCurrentText(style)
                except Exception:
                    pass
            # axes labels/title/limits
            if hasattr(self, "ax") and self.ax is not None:
                # Restore labels and font if available
                if "xlabel" in cfg:
                    f = cfg.get("xlabel_font", {})
                    self.ax.set_xlabel(cfg["xlabel"],
                        fontname=f.get("name", "Arial"),
                        fontsize=f.get("size", 12),
                        fontweight=f.get("weight", "normal"),
                        fontstyle=f.get("style", "normal"))
                if "ylabel" in cfg:
                    f = cfg.get("ylabel_font", {})
                    self.ax.set_ylabel(cfg["ylabel"],
                        fontname=f.get("name", "Arial"),
                        fontsize=f.get("size", 12),
                        fontweight=f.get("weight", "normal"),
                        fontstyle=f.get("style", "normal"))
                if "title" in cfg:
                    f = cfg.get("title_font", {})
                    self.ax.set_title(cfg["title"],
                        fontname=f.get("name", "Arial"),
                        fontsize=f.get("size", 12),
                        fontweight=f.get("weight", "normal"),
                        fontstyle=f.get("style", "normal"))
                if "xlim"   in cfg: self.ax.set_xlim(*cfg["xlim"])
                if "ylim"   in cfg: self.ax.set_ylim(*cfg["ylim"])
            # Restore UI font if saved, otherwise derive from xlabel_font
            ui_f = cfg.get("ui_font")
            if ui_f and (ui_f.get("name") or ui_f.get("size") is not None):
                fname = ui_f.get("name") or cfg.get("xlabel_font", {}).get("name", "DejaVu Sans")
                fsize = ui_f.get("size") if ui_f.get("size") is not None else int(cfg.get("xlabel_font", {}).get("size", 12))
            else:
                xf = cfg.get("xlabel_font", {})
                fname = xf.get("name", "DejaVu Sans")
                fsize = int(xf.get("size", 12))
            # Sync UI widgets
            if hasattr(self, 'font_combo'):
                idx = self.font_combo.findText(fname)
                if idx >= 0:
                    self.font_combo.setCurrentIndex(idx)
            if hasattr(self, 'font_size_input'):
                self.font_size_input.setText(str(fsize))
            # Apply fonts to axes/ticks/legend
            self.apply_font_settings(fname, fsize)
            # keep UI inputs in sync with current axes state
            if hasattr(self, "xlabel_input"):
                self.xlabel_input.setText(self.ax.get_xlabel())
            if hasattr(self, "ylabel_input"):
                self.ylabel_input.setText(self.ax.get_ylabel())
            # grid
            self._xrd_grid_state = bool(cfg.get("grid", False))
            if hasattr(self, "ax") and self.ax is not None:
                self.ax.grid(self._xrd_grid_state)
            # legend prefs
            self.legend_location = cfg.get("legend_location", getattr(self, "legend_location", "best"))
            self.legend_custom_order = cfg.get("legend_custom_order", None)
            # datasets: apply color/offset by filename match (if any)
            ds_cfg = {d["filename"]: d for d in cfg.get("datasets", []) if d.get("filename")}
            if hasattr(self, "xrd_datasets"):
                for d in self.xrd_datasets:
                    fn = d.get("filename")
                    if fn in ds_cfg:
                        d["color"] = ds_cfg[fn].get("color", d.get("color"))
                        d["offset"] = ds_cfg[fn].get("offset", d.get("offset", 0.0))
                self.redraw_plot()
            else:
                if hasattr(self, "canvas"):
                    self.canvas.draw()
            # update legend with possible custom order
            self.update_legend()
            QMessageBox.information(self, "Bilgi", "Ayarlar yüklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar uygulanamadı:\n{e}")

    def apply_font_settings(self, font_name, font_size):
        """Apply font settings to axes labels, title, tick labels, and legend.
        Also sync the UI controls to reflect the current choice.
        """
        if hasattr(self, "ax") and self.ax is not None:
            # Axis labels & title
            self.ax.xaxis.label.set_fontname(font_name)
            self.ax.xaxis.label.set_fontsize(font_size)
            self.ax.yaxis.label.set_fontname(font_name)
            self.ax.yaxis.label.set_fontsize(font_size)
            self.ax.title.set_fontname(font_name)
            self.ax.title.set_fontsize(font_size)
            # Tick labels (x & y)
            try:
                for lab in self.ax.get_xticklabels():
                    lab.set_fontname(font_name)
                    lab.set_fontsize(font_size)
                for lab in self.ax.get_yticklabels():
                    lab.set_fontname(font_name)
                    lab.set_fontsize(font_size)
            except Exception:
                pass
            # Legend texts (if any)
            try:
                for legend in [getattr(self, 'legend1', None), getattr(self, 'legend2', None)]:
                    if legend:
                        for text in legend.get_texts():
                            text.set_fontname(font_name)
                            text.set_fontsize(font_size)
            except Exception:
                pass
        # Sync UI controls
        if hasattr(self, "font_combo"):
            idx = self.font_combo.findText(font_name)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
        if hasattr(self, "font_size_input"):
            self.font_size_input.setText(str(font_size))
        if hasattr(self, 'canvas'):
            try:
                self.canvas.draw()
            except Exception:
                pass

    def open_xrd_data_table_entry(self):
        """
        Güvenli giriş noktası: Eğer gelişmiş tablo editörü (open_xrd_data_table)
        tanımlıysa onu çağırır; yoksa tek veri için basit bir editör açar.
        """
        # Gelişmiş editör varsa onu kullan
        if hasattr(self, "open_xrd_data_table"):
            try:
                return self.open_xrd_data_table()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Veri tablosu açılamadı:\n{e}")
                return

        # ---- Basit fallback editör (tek df) ----
        if not hasattr(self, "df") or self.df is None:
            QMessageBox.warning(self, "Uyarı", "Önce en az bir XRD verisi yükleyin.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("XRD Veri Tablosu (Basit)")
        vbox = QVBoxLayout(dlg)
        table = QTableWidget()
        table.setRowCount(len(self.df))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["X", "Y"])
        for i in range(len(self.df)):
            table.setItem(i, 0, QTableWidgetItem(str(self.df.iloc[i, 0])))
            table.setItem(i, 1, QTableWidgetItem(str(self.df.iloc[i, 1])))
        vbox.addWidget(table)

        h = QHBoxLayout()
        btn_add_row = QPushButton("Satır Ekle")
        btn_insert_row = QPushButton("Seçili Üstüne Ekle")
        btn_del_rows = QPushButton("Seçili Satır(ları) Sil")
        btn_add_col = QPushButton("Sütun Ekle")
        btn_apply = QPushButton("Uygula")
        btn_close = QPushButton("Kapat")
        h.addStretch()
        h.addWidget(btn_add_row)
        h.addWidget(btn_insert_row)
        h.addWidget(btn_del_rows)
        h.addWidget(btn_add_col)
        h.addWidget(btn_apply)
        h.addWidget(btn_close)
        vbox.addLayout(h)

        def apply_changes():
            n = table.rowCount()
            xs, ys = [], []
            for r in range(n):
                xv = table.item(r, 0).text() if table.item(r, 0) else "0"
                yv = table.item(r, 1).text() if table.item(r, 1) else "0"
                try:
                    xs.append(float(xv))
                except Exception:
                    xs.append(np.nan)
                try:
                    ys.append(float(yv))
                except Exception:
                    ys.append(np.nan)
            new_df = pd.DataFrame({0: xs, 1: ys})
            # Güncellenen veriyi hem self.df'ye hem de varsa xrd_datasets'e yaz
            self.df = new_df
            if hasattr(self, "xrd_datasets") and self.xrd_datasets:
                # Varsayılan: ilk dataset düzenleniyor (fallback editör)
                self.xrd_datasets[0]["df"] = new_df.copy()
                if "orig_df" in self.xrd_datasets[0]:
                    self.xrd_datasets[0]["orig_df"] = new_df.copy()
                # Tüm datasetler modundaysak yeniden çiz
                self.redraw_plot()
            else:
                # Tek dataset akışı
                self.update_graph_from_df()
            dlg.close()

        def add_row():
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(""))
            table.setItem(r, 1, QTableWidgetItem(""))

        def insert_row_above():
            sel = table.selectionModel().selectedRows()
            if not sel:
                add_row()
                return
            # insert above the first selected row
            r0 = min(idx.row() for idx in sel)
            table.insertRow(r0)
            table.setItem(r0, 0, QTableWidgetItem(""))
            table.setItem(r0, 1, QTableWidgetItem(""))

        def delete_selected_rows():
            sel = sorted({idx.row() for idx in table.selectionModel().selectedRows()}, reverse=True)
            for r in sel:
                table.removeRow(r)

        def add_column_warn():
            QMessageBox.information(self, "Bilgi",
                                    "XRD veri tablosunda sadece 2 sütun (X ve Y) desteklenir.\n"
                                    "Sütun ekleme XRD modunda devre dışıdır.")

        btn_apply.clicked.connect(apply_changes)
        btn_close.clicked.connect(dlg.close)
        btn_add_row.clicked.connect(add_row)
        btn_insert_row.clicked.connect(insert_row_above)
        btn_del_rows.clicked.connect(delete_selected_rows)
        btn_add_col.clicked.connect(add_column_warn)
        dlg.resize(800, 600)
        dlg.exec_()

    def open_xrd_data_table(self):
        """
        Gelişmiş veri tablosu: Birden fazla XRD varsa önce hangisi düzenlenecek
        diye sorar; seçilen dataset'in X/Y değerlerini tabloya getirir.
        """
        # Dataset kontrolü
        if not hasattr(self, "xrd_datasets") or len(self.xrd_datasets) == 0:
            QMessageBox.warning(self, "Uyarı", "Önce en az bir XRD verisi yükleyin.")
            return

        # Hangi dataset?
        target_idx = 0
        if len(self.xrd_datasets) > 1:
            names = [d.get("filename", f"Dataset {i+1}") for i, d in enumerate(self.xrd_datasets)]
            name, ok = QInputDialog.getItem(self, "Veri Seç", "Hangi XRD'yi düzenlemek istiyorsun?", names, 0, False)
            if not ok:
                return
            target_idx = names.index(name)

        d = self.xrd_datasets[target_idx]
        df = d["df"]

        # Dialog ve tablo
        dlg = QDialog(self)
        dlg.setWindowTitle(f"XRD Veri Tablosu — {d.get('filename','Dataset')}")
        vbox = QVBoxLayout(dlg)
        table = QTableWidget()
        table.setRowCount(len(df))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["X", "Y"])
        for i in range(len(df)):
            table.setItem(i, 0, QTableWidgetItem(str(df.iloc[i, 0])))
            table.setItem(i, 1, QTableWidgetItem(str(df.iloc[i, 1])))
        vbox.addWidget(table)

        # Butonlar
        h = QHBoxLayout()
        btn_add_row = QPushButton("Satır Ekle")
        btn_insert_row = QPushButton("Seçili Üstüne Ekle")
        btn_del_rows = QPushButton("Seçili Satır(ları) Sil")
        btn_add_col = QPushButton("Sütun Ekle")
        btn_apply = QPushButton("Uygula")
        btn_close = QPushButton("Kapat")
        h.addStretch()
        h.addWidget(btn_add_row)
        h.addWidget(btn_insert_row)
        h.addWidget(btn_del_rows)
        h.addWidget(btn_add_col)
        h.addWidget(btn_apply)
        h.addWidget(btn_close)
        vbox.addLayout(h)

        def apply_changes():
            n = table.rowCount()
            xs, ys = [], []
            for r in range(n):
                xv = table.item(r, 0).text() if table.item(r, 0) else "0"
                yv = table.item(r, 1).text() if table.item(r, 1) else "0"
                try:
                    xs.append(float(xv))
                except Exception:
                    xs.append(np.nan)
                try:
                    ys.append(float(yv))
                except Exception:
                    ys.append(np.nan)
            new_df = pd.DataFrame({0: xs, 1: ys})
            # Seçilen dataset'i güncelle
            self.xrd_datasets[target_idx]["df"] = new_df.copy()
            if "orig_df" in self.xrd_datasets[target_idx]:
                self.xrd_datasets[target_idx]["orig_df"] = new_df.copy()
            # Eğer seçilen dataset ana df ile aynıysa self.df'yi de güncelle
            try:
                main_name = getattr(self, "main_filename", None)
                if main_name and d.get("filename") == main_name:
                    self.df = new_df.copy()
            except Exception:
                pass
            self.redraw_plot()
            dlg.close()

        def add_row():
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(""))
            table.setItem(r, 1, QTableWidgetItem(""))

        def insert_row_above():
            sel = table.selectionModel().selectedRows()
            if not sel:
                add_row()
                return
            r0 = min(idx.row() for idx in sel)
            table.insertRow(r0)
            table.setItem(r0, 0, QTableWidgetItem(""))
            table.setItem(r0, 1, QTableWidgetItem(""))

        def delete_selected_rows():
            sel = sorted({idx.row() for idx in table.selectionModel().selectedRows()}, reverse=True)
            for r in sel:
                table.removeRow(r)

        def add_column_warn():
            QMessageBox.information(self, "Bilgi",
                                    "XRD veri tablosunda sadece 2 sütun (X ve Y) desteklenir.\n"
                                    "Sütun ekleme XRD modunda devre dışıdır.")

        btn_apply.clicked.connect(apply_changes)
        btn_close.clicked.connect(dlg.close)
        btn_add_row.clicked.connect(add_row)
        btn_insert_row.clicked.connect(insert_row_above)
        btn_del_rows.clicked.connect(delete_selected_rows)
        btn_add_col.clicked.connect(add_column_warn)
        dlg.resize(900, 600)
        dlg.exec_()

    def on_pick(self, event):
        obj = event.artist
        if hasattr(obj, 'get_text'):
            current_text = obj.get_text()
            # Check for tick labels
            axis_type = None
            if obj in self.ax1.get_xticklabels():
                axis_type = 'x'
                all_labels = self.ax1.get_xticklabels()
            elif obj in self.ax1.get_yticklabels():
                axis_type = 'y1'
                all_labels = self.ax1.get_yticklabels()
            elif obj in self.ax2.get_yticklabels():
                axis_type = 'y2'
                all_labels = self.ax2.get_yticklabels()
            # Axis label handling
            elif obj is self.ax1.xaxis.label:
                font, ok = QFontDialog.getFont()
                if ok:
                    color = QColorDialog.getColor()
                    color_hex = color.name() if color.isValid() else 'black'
                    self.ax1.set_xlabel(
                        self.ax1.get_xlabel(),
                        fontsize=font.pointSize(),
                        fontname=font.family(),
                        fontweight=font.weight(),
                        color=color_hex
                    )
                    self.canvas.draw()
                return
            elif obj is self.ax1.yaxis.label:
                font, ok = QFontDialog.getFont()
                if ok:
                    color = QColorDialog.getColor()
                    color_hex = color.name() if color.isValid() else 'black'
                    self.ax1.set_ylabel(
                        self.ax1.get_ylabel(),
                        fontsize=font.pointSize(),
                        fontname=font.family(),
                        fontweight=font.weight(),
                        color=color_hex
                    )
                    self.canvas.draw()
                return
            elif obj is self.ax2.yaxis.label:
                font, ok = QFontDialog.getFont()
                if ok:
                    color = QColorDialog.getColor()
                    color_hex = color.name() if color.isValid() else 'black'
                    self.ax2.set_ylabel(
                        self.ax2.get_ylabel(),
                        fontsize=font.pointSize(),
                        fontname=font.family(),
                        fontweight=font.weight(),
                        color=color_hex
                    )
                    self.canvas.draw()
                return
            else:
                return

            font, ok = QFontDialog.getFont()
            if ok:
                for label in all_labels:
                    label.set_fontsize(font.pointSize())
                    label.set_fontname(font.family())
                    label.set_fontweight(font.weight())
                self.canvas.draw()

    def toggle_figure_size(self):
        if not hasattr(self, 'fullscreen_mode'):
            self.fullscreen_mode = False
        if not self.fullscreen_mode:
            self.figure.set_size_inches(10, 7.5)  # Full-size view
            self.fullscreen_mode = True
        else:
            self.figure.set_size_inches(6, 4.5)  # Reset to original size
            self.fullscreen_mode = False
        self.canvas.draw()


    def dosya_yukle(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Dosya Seç", "", "Excel Files (*.xlsx *.xls);;Text Files (*.txt *.csv)")
        if filename:
            if filename.endswith(('.xlsx', '.xls')):
                self.df = pd.read_excel(filename)
                self.current_filename = filename.split("/")[-1]
            else:
                self.df = pd.read_csv(filename)
            self.update_graph_from_df()

    def update_graph_from_df(self):
        # For XRD, clear ax1 if no xrd_datasets or user hit clear
        # If using xrd_datasets, redraw all
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            self.redraw_plot()
            return
        # Fallback: original behavior for single dataset
        self.ax.clear()
        try:
            if all(col in self.df.columns for col in ['Time', 'Temperature', 'Displacement']):
                self.temp_line, = self.ax.plot(self.df['Time'], self.df['Temperature'], '-', color='blue', linewidth=3.5, label='Temperature')
                self.ax.set_xlabel('Sintering Time (seconds)', fontsize=14, fontweight='bold', color='black')
                self.ax.set_ylabel('Temperature (°C)', fontsize=14, fontweight='bold', color='blue')
            else:
                x = self.df.iloc[:, 0]
                y = self.df.iloc[:, 1]
                self.ax.plot(x, y, '-', linewidth=2.0, label="XRD", color='blue')
                if hasattr(self, 'peak_toggle') and self.peak_toggle.isChecked():
                    try:
                        peaks, _ = find_peaks(y, height=50)
                        self.ax.plot(x.iloc[peaks] if hasattr(x, 'iloc') else x[peaks],
                                     (y.iloc[peaks] if hasattr(y, 'iloc') else y[peaks]),
                                     'ro', label='Detected Peaks')
                        for peak in peaks:
                            xpos = x.iloc[peak] if hasattr(x, 'iloc') else x[peak]
                            ypos = y.iloc[peak] if hasattr(y, 'iloc') else y[peak]
                            self.ax.annotate(f"{xpos:.2f}", (xpos, ypos), textcoords="offset points", xytext=(0,5), ha='center', fontsize=8, color='black')
                    except Exception as e:
                        print("Peak detection error:", e)
                self.ax.set_xlabel(self.df.columns[0], fontsize=14, fontweight='bold')
                self.ax.set_ylabel("Intensity", fontsize=14, fontweight='bold')
            self.ax.tick_params(axis='both', labelsize=12, width=2)
            self.ax.grid(False)
            self.ax.legend()
            self.canvas.draw()
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Hata", f"Grafik çizimi sırasında hata oluştu:\n{str(e)}")

    def set_y2_tick_format(self):
        fmt, ok = QInputDialog.getText(self, "Y2 Tick Formatı", "Tick formatını girin (örnek: %.2f):", text=self.y2_tick_format)
        if ok and fmt.startswith('%'):
            self.y2_tick_format = fmt
            self.ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter(self.y2_tick_format))
            self.canvas.draw()


    def open_data_editor(self):
        self.editor_window = QWidget()
        self.editor_window.setWindowTitle("Verileri Düzenle")
        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setRowCount(len(self.df))
        self.table.setColumnCount(len(self.df.columns))
        self.table.setHorizontalHeaderLabels(self.df.columns)

        for i in range(len(self.df)):
            for j in range(len(self.df.columns)):
                item = QTableWidgetItem(str(self.df.iloc[i, j]))
                self.table.setItem(i, j, item)

        layout.addWidget(self.table)

        save_btn = QPushButton("Güncellemeleri Uygula")
        save_btn.clicked.connect(self.apply_table_changes)
        layout.addWidget(save_btn)

        self.editor_window.setLayout(layout)
        self.editor_window.resize(800, 600)
        self.editor_window.show()


    def apply_table_changes(self):
        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if item is not None:
                    value = item.text()
                    try:
                        self.df.iat[i, j] = float(value)
                    except ValueError:
                        self.df.iat[i, j] = value  # Allow non-numeric if applicable

        self.update_graph_from_df()
        self.canvas.draw()
        self.editor_window.close()


    def save_data_to_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Veriyi Kaydet", "", "Excel Files (*.xlsx);;CSV Files (*.csv)")
        if filename:
            if filename.endswith('.xlsx'):
                self.df.to_excel(filename, index=False)
            else:
                self.df.to_csv(filename, index=False)


    def save_state(self):
        self.previous_state = {
            "temp_color": self.temp_line.get_color(),
            "disp_color": self.disp_line.get_color(),
            "temp_width": self.temp_line.get_linewidth(),
            "disp_width": self.disp_line.get_linewidth(),
            "xlabel": self.ax1.get_xlabel(),
            "ylabel1": self.ax1.get_ylabel(),
            "ylabel2": self.ax2.get_ylabel(),
            "bg_color": self.figure.get_facecolor(),
            "grid": self.grid_state,
            "title": self.ax1.get_title()
        }

    def undo_changes(self):
        if not self.previous_state:
            return
        self.temp_line.set_color(self.previous_state["temp_color"])
        self.disp_line.set_color(self.previous_state["disp_color"])
        self.temp_line.set_linewidth(self.previous_state["temp_width"])
        self.disp_line.set_linewidth(self.previous_state["disp_width"])
        self.ax1.set_xlabel(self.previous_state["xlabel"])
        self.ax1.set_ylabel(self.previous_state["ylabel1"])
        self.ax2.set_ylabel(self.previous_state["ylabel2"])
        self.figure.patch.set_facecolor(self.previous_state["bg_color"])
        self.ax1.set_facecolor(self.previous_state["bg_color"])
        self.ax2.set_facecolor(self.previous_state["bg_color"])
        self.grid_state = self.previous_state["grid"]
        self.ax1.grid(self.grid_state)
        self.ax1.set_title(self.previous_state["title"])
        self.canvas.draw()
        self.update_legend()

    # --- Additional methods for RenkDegistirici ---
    def add_row_to_table(self):
        # Add a new row with zeros for all columns
        self.df.loc[len(self.df)] = [0] * len(self.df.columns)
        self.open_data_editor()

    def delete_selected_row(self):
        # Remove the selected row from the table and dataframe
        selected = self.table.currentRow()
        if selected >= 0:
            self.df.drop(self.df.index[selected], inplace=True)
            self.df.reset_index(drop=True, inplace=True)
            self.open_data_editor()

    def filter_data_by_time(self):
        min_time, ok1 = QInputDialog.getDouble(self, "Alt Zaman Sınırı", "Minimum Time:", decimals=2)
        max_time, ok2 = QInputDialog.getDouble(self, "Üst Zaman Sınırı", "Maximum Time:", decimals=2)
        if ok1 and ok2:
            filtered_df = self.df[(self.df['Time'] >= min_time) & (self.df['Time'] <= max_time)].copy()
            self.df = filtered_df.reset_index(drop=True)
            self.update_graph_from_df()

    def load_comparison_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Dosya Seç (Karşılaştırma)", "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)")
        if filename:
            if filename.endswith(('.xlsx', '.xls')):
                compare_df = pd.read_excel(filename)
            else:
                compare_df = pd.read_csv(filename)
            self.ax1.plot(compare_df['Time'], compare_df['Temperature'], '--', color='green', linewidth=2, label='Karşılaştırma Temp')
            self.ax2.plot(compare_df['Time'], compare_df['Displacement'], '--', color='purple', linewidth=2, label='Karşılaştırma Disp')
            self.canvas.draw()
            self.update_legend()

    def highlight_data_point(self):
        value, ok = QInputDialog.getDouble(self, "Vurgulanacak Zaman", "Time Değeri:", decimals=2)
        if ok:
            nearest_index = (self.df['Time'] - value).abs().idxmin()
            x = self.df.loc[nearest_index, 'Time']
            y_temp = self.df.loc[nearest_index, 'Temperature']
            y_disp = self.df.loc[nearest_index, 'Displacement']
            self.ax1.plot(x, y_temp, 'o', color='blue', markersize=10, label='Vurgulu Temp')
            self.ax2.plot(x, y_disp, 'o', color='red', markersize=10, label='Vurgulu Disp')
            self.canvas.draw()
            self.update_legend()

    def add_trend_line(self):
        degree, ok = QInputDialog.getInt(self, "Trend Çizgisi Derecesi", "Polinom Derecesi:", 1, 1, 5)
        if ok:
            time_vals = self.df['Time'].values
            temp_vals = self.df['Temperature'].values
            coeffs = np.polyfit(time_vals, temp_vals, degree)
            trend = np.poly1d(coeffs)
            self.ax1.plot(time_vals, trend(time_vals), '-', linewidth=2, label=f'Trend Temp (deg={degree})')
            self.canvas.draw()
            self.update_legend()

    def clear_overlays(self):
        self.update_graph_from_df()

    def save_preset(self):
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        fname, _ = QFileDialog.getSaveFileName(self, "Stili Kaydet", "", "JSON Files (*.json)")
        if not fname:
            return
        lines_y1 = self.ax1.get_lines()
        lines_y2 = self.ax2.get_lines()

        config = {
            "title": self.ax1.get_title(),
            "xlabel": self.ax1.get_xlabel(),
            "ylabel": self.ax1.get_ylabel(),
            "y2label": self.ax2.get_ylabel(),
            "tick_format_y2": self.y2_tick_format,
            "y1_line_color": lines_y1[0].get_color() if lines_y1 else None,
            "y1_linewidth": lines_y1[0].get_linewidth() if lines_y1 else None,
            "y2_line_color": lines_y2[0].get_color() if lines_y2 else None,
            "y2_linewidth": lines_y2[0].get_linewidth() if lines_y2 else None,
            "font_family": self.ax1.xaxis.label.get_fontfamily()[0] if self.ax1.xaxis.label.get_fontfamily() else None,
            "font_size": self.ax1.xaxis.label.get_fontsize()
        }

        with open(fname, 'w') as f:
            json.dump(config, f, indent=4)
        QMessageBox.information(self, "Bilgi", "Stil başarıyla kaydedildi.")

    def load_preset(self):
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        fname, _ = QFileDialog.getOpenFileName(self, "Stil Dosyasını Aç", "", "JSON Files (*.json)")
        if not fname:
            return
        with open(fname, 'r') as f:
            config = json.load(f)

        self.ax1.set_title(config.get("title", ""))
        self.ax1.set_xlabel(config.get("xlabel", ""))
        self.ax1.set_ylabel(config.get("ylabel", ""))
        self.ax2.set_ylabel(config.get("y2label", ""))
        self.y2_tick_format = config.get("tick_format_y2", '%.3f')
        self.ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter(self.y2_tick_format))

        if "y1_line_color" in config:
            for line in self.ax1.get_lines():
                if config["y1_line_color"] is not None:
                    line.set_color(config["y1_line_color"])
                if config.get("y1_linewidth") is not None:
                    line.set_linewidth(config.get("y1_linewidth", 1.5))
        if "y2_line_color" in config:
            for line in self.ax2.get_lines():
                if config["y2_line_color"] is not None:
                    line.set_color(config["y2_line_color"])
                if config.get("y2_linewidth") is not None:
                    line.set_linewidth(config.get("y2_linewidth", 1.5))

        font = {
            "family": config.get("font_family", "Arial"),
            "size": config.get("font_size", 12)
        }
        # Apply font to axis titles and labels
        self.ax1.set_title(self.ax1.get_title(), fontdict=font)
        self.ax1.set_xlabel(self.ax1.get_xlabel(), fontdict=font)
        self.ax1.set_ylabel(self.ax1.get_ylabel(), fontdict=font)
        self.ax2.set_ylabel(self.ax2.get_ylabel(), fontdict=font)

        self.canvas.draw()

    def export_figure(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Grafiği Kaydet", "", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if fname:
            self.figure.savefig(fname, dpi=600, bbox_inches='tight')

    def add_vertical_lines(self):
        text, ok = QInputDialog.getText(self, "Dikey Çizgi(ler)", "X konum(lar)ını virgülle ayırarak girin (örn: 10, 27.5, 43):")
        if not ok or not text.strip():
            return
        xs = []
        for part in text.split(','):
            try:
                xs.append(float(part.strip()))
            except ValueError:
                pass
        if not hasattr(self, "vlines"):
            self.vlines = []
        for xv in xs:
            ln = self.ax.axvline(x=xv, linestyle='--', color='k', linewidth=1.2, alpha=0.8)
            self.vlines.append(ln)
        self.canvas.draw()

    def clear_vertical_lines(self):
        if hasattr(self, "vlines"):
            for ln in self.vlines:
                try:
                    ln.remove()
                except Exception:
                    pass
            self.vlines = []
            self.canvas.draw()

    def on_mouse_move(self, event):
        if not hasattr(self, "status_label"):
            return
        if event.xdata is None or event.ydata is None:
            self.status_label.setText("x: -, y: -")
        else:
            self.status_label.setText(f"x: {event.xdata:.2f}, y: {event.ydata:.2f}")
    def legend_handle_linewidth(self):
        lw, ok = QInputDialog.getDouble(self, "Gösterge Kalınlığı", "LineWidth:", 2.0, 0.1, 10.0, 1)
        if not ok:
            return
        for line in self.ax.get_lines():
            line.set_linewidth(lw)
        self.canvas.draw()
        self.update_legend()

    def legend_handle_color(self):
        color = self.get_color_input("Gösterge Rengi", default="#000000")
        if not color:
            return
        for line in self.ax.get_lines():
            line.set_color(color)
        self.canvas.draw()
        self.update_legend()

    def legend_handle_markersize(self):
        size, ok = QInputDialog.getDouble(self, "Gösterge Büyüklüğü (marker)", "Marker size:", 6.0, 1.0, 30.0, 1)
        if not ok:
            return
        for line in self.ax.get_lines():
            try:
                line.set_markersize(size)
            except Exception:
                pass
        self.canvas.draw()
        self.update_legend()

    def legend_text_weight(self):
        choice, ok = QInputDialog.getItem(self, "Legend Yazı Kalınlığı", "Seç:", ["normal", "bold"], 0, False)
        if not ok:
            return
        for legend in [self.legend1, self.legend2]:
            if legend:
                for text in legend.get_texts():
                    text.set_fontweight(choice)
        self.canvas.draw()

    def legend_position_by_coords(self):
        x, ok1 = QInputDialog.getDouble(self, "Legend X (0-1)", "x:", 0.95, 0.0, 1.0, 2)
        if not ok1:
            return
        y, ok2 = QInputDialog.getDouble(self, "Legend Y (0-1)", "y:", 0.95, 0.0, 1.0, 2)
        if not ok2:
            return
        leg = self.ax.legend(loc='center', bbox_to_anchor=(x, y), frameon=True)
        self.legend1 = leg
        self.legend2 = leg
        self.canvas.draw()

    def legend_reorder_dialog(self):
        # Get current labels from ax (ignore internal)
        h, l = self.ax.get_legend_handles_labels() if hasattr(self, 'ax') else ([], [])
        labels = [lbl for lbl in l if lbl and not lbl.startswith('_')]
        if not labels:
            QMessageBox.information(self, "Bilgi", "Önce grafikte bir veya daha fazla eğri olmalı.")
            return

        # Ask for new order as comma-separated list
        default_text = ", ".join(labels)
        text, ok = QInputDialog.getText(self, "Legend Sırası", "Etiketleri istediğiniz sırayla, virgülle ayırarak girin:", text=default_text)
        if not ok:
            return
        new_order = [t.strip() for t in text.split(",") if t.strip()]

        # Ask for compact placement
        pos_choice, ok2 = QInputDialog.getItem(self, "Legend Konumu", "Seç:", ["Üst", "Orta", "Alt", "Mevcut"], 0, False)
        if not ok2:
            return
        if pos_choice == "Üst":
            self.legend_location = "upper center"
        elif pos_choice == "Orta":
            self.legend_location = "center"
        elif pos_choice == "Alt":
            self.legend_location = "lower center"
        # if "Mevcut", keep current

        # Save order and update
        self.legend_custom_order = new_order
        self.update_legend()
    def axis_set_label(self, axis):
        text, ok = QInputDialog.getText(self, f"{axis.upper()} Eksen İsmi", "Etiket girin:")
        if not ok:
            return
        if axis == 'x':
            self.ax.set_xlabel(text)
        else:
            self.ax.set_ylabel(text)
        self.canvas.draw()

    def axis_set_label_font(self, axis):
        font, ok = QFontDialog.getFont()
        if not ok:
            return
        if axis == 'x':
            self.ax.set_xlabel(self.ax.get_xlabel(), fontname=font.family(), fontsize=font.pointSize(), fontweight=font.weight())
        else:
            self.ax.set_ylabel(self.ax.get_ylabel(), fontname=font.family(), fontsize=font.pointSize(), fontweight=font.weight())
        self.canvas.draw()

    def axis_set_label_pos(self, axis):
        x, ok1 = QInputDialog.getDouble(self, f"{axis.upper()} Etiket X (0-1)", "x:", 0.5, 0.0, 1.0, 2)
        if not ok1:
            return
        y_default = -0.05 if axis=='x' else 0.5
        y, ok2 = QInputDialog.getDouble(self, f"{axis.upper()} Etiket Y (0-1)", "y:", y_default, -1.0, 2.0, 2)
        if not ok2:
            return
        if axis == 'x':
            self.ax.xaxis.set_label_coords(x, y)
        else:
            self.ax.yaxis.set_label_coords(x, y)
        self.canvas.draw()

    def axis_spine_width(self, axis):
        width, ok = QInputDialog.getDouble(self, f"{axis.upper()} Çizgi Kalınlığı", "Kalınlık:", 1.5, 0.1, 10.0, 1)
        if not ok:
            return
        if axis == 'x':
            self.ax.spines['bottom'].set_linewidth(width)
        else:
            self.ax.spines['left'].set_linewidth(width)
        self.canvas.draw()

    def axis_set_tick_locator(self, axis):
        major, ok1 = QInputDialog.getDouble(self, f"{axis.upper()} Major Aralık", "Adım:", 5.0, 0.01, 1000.0, 2)
        if not ok1:
            return
        minor, ok2 = QInputDialog.getDouble(self, f"{axis.upper()} Minor Aralık", "Adım:", 1.0, 0.001, 1000.0, 3)
        if not ok2:
            return
        if axis == 'x':
            self.ax.xaxis.set_major_locator(ticker.MultipleLocator(major))
            self.ax.xaxis.set_minor_locator(ticker.MultipleLocator(minor))
        else:
            self.ax.yaxis.set_major_locator(ticker.MultipleLocator(major))
            self.ax.yaxis.set_minor_locator(ticker.MultipleLocator(minor))
        self.canvas.draw()

    def axis_tick_style(self, axis):
        width, ok1 = QInputDialog.getDouble(self, f"{axis.upper()} Tick Kalınlığı", "Kalınlık:", 1.0, 0.1, 10.0, 1)
        if not ok1:
            return
        color = self.get_color_input(f"{axis.upper()} Tick Rengi", default="#000000")
        if not color:
            return
        self.ax.tick_params(axis=axis, width=width, colors=color)
        self.canvas.draw()

    def axis_tick_label_font(self, axis):
        font, ok = QFontDialog.getFont()
        if not ok:
            return
        labels = self.ax.get_xticklabels() if axis == 'x' else self.ax.get_yticklabels()
        for lab in labels:
            lab.set_fontname(font.family())
            lab.set_fontsize(font.pointSize())
            lab.set_fontweight(font.weight())
        self.canvas.draw()
    def apply_theme_from_combo(self):
        try:
            style = self.theme_combo.currentText()
            plt.style.use(style)
            if hasattr(self, "xrd_datasets") and self.xrd_datasets:
                self.redraw_plot()
            else:
                self.update_graph_from_df()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tema uygulanamadı:\n{str(e)}")

    # ---------- Ön işleme: yardımcılar ----------
    def _ensure_backup(self):
        """Keep a copy of original data to allow reset."""
        if not hasattr(self, "_orig_df") or self._orig_df is None:
            if hasattr(self, "df") and self.df is not None:
                self._orig_df = self.df.copy()
        # for multi-datasets
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            for d in self.xrd_datasets:
                if "orig_df" not in d or d["orig_df"] is None:
                    d["orig_df"] = d["df"].copy()

    def _select_dataset_index(self):
        """Return -1 for 'all datasets', or an index into self.xrd_datasets; None if cancelled."""
        if not hasattr(self, "xrd_datasets") or not self.xrd_datasets:
            return None
        items = ["Tüm Datasetler"] + [d.get("filename", f"Dataset {i}") for i, d in enumerate(self.xrd_datasets)]
        choice, ok = QInputDialog.getItem(self, "Hedef Dataset", "Uygulanacak veri:", items, 0, False)
        if not ok:
            return None
        return -1 if choice == "Tüm Datasetler" else items.index(choice) - 1

    def _apply_to_all(self, transform_fn):
        """Apply a y -> transform(y) to active data.
        If multiple datasets are loaded, apply to all; otherwise apply to main df."""
        self._ensure_backup()
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            for d in self.xrd_datasets:
                df = d["df"]
                y = df.iloc[:, 1].to_numpy()
                newy = transform_fn(y)
                d["df"].iloc[:, 1] = newy
            self.redraw_plot()
        else:
            y = self.df.iloc[:, 1].to_numpy()
            newy = transform_fn(y)
            self.df.iloc[:, 1] = newy
            self.update_graph_from_df()

    def _draw_background(self, x, bg):
        """Draw (or update) a dashed background curve for single-dataset mode."""
        if not hasattr(self, "_bg_visible"):
            self._bg_visible = True
        self._bg_x = x
        self._bg_y = bg
        # remove existing bg line if any
        if hasattr(self, "_bg_line") and self._bg_line is not None:
            try:
                self._bg_line.remove()
            except Exception:
                pass
            self._bg_line = None
        if self._bg_visible:
            self._bg_line, = self.ax.plot(x, bg, '--', color='gray', linewidth=1.2, label='Background')
            self.ax.legend()
        self.canvas.draw()

    def toggle_background_curve(self):
        """Show/hide stored background curve."""
        if not hasattr(self, "_bg_visible"):
            self._bg_visible = True
        self._bg_visible = not self._bg_visible
        if hasattr(self, "_bg_line") and self._bg_line is not None:
            self._bg_line.set_visible(self._bg_visible)
            self.canvas.draw()

    # ---------- Yumuşatma ----------
    def preprocess_savgol(self):
        """Savitzky–Golay smoothing on current data."""
        try:
            win, ok1 = QInputDialog.getInt(self, "Savitzky–Golay", "Pencere (tek sayı):", 11, 3, 301, 2)
            if not ok1:
                return
            if win % 2 == 0:
                win += 1
            poly, ok2 = QInputDialog.getInt(self, "Savitzky–Golay", "Polinom derecesi:", 3, 1, 7, 1)
            if not ok2:
                return
            def fn(y):
                return savgol_filter(y, window_length=win, polyorder=poly)
            target_idx = self._select_dataset_index()
            self._ensure_backup()
            if target_idx is None:
                # no multi-dataset, apply to main df
                self._apply_to_all(fn)
            elif target_idx == -1:
                # all datasets
                self._apply_to_all(fn)
            else:
                # single dataset
                d = self.xrd_datasets[target_idx]
                y_arr = d["df"].iloc[:, 1].to_numpy()
                d["df"].iloc[:, 1] = fn(y_arr)
                self.redraw_plot()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yumuşatma uygulanamadı:\n{e}")

    # ---------- Arka plan çıkarma: Asymmetric Least Squares (ALS) ----------
    def _baseline_als(self, y, lam=1e5, p=0.01, niter=10):
        """Return baseline using Asymmetric Least Squares (Eilers & Boelens, 2005)."""
        L = len(y)
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L-2)).T
        w = np.ones(L)
        for _ in range(niter):
            W = sparse.spdiags(w, 0, L, L)
            Z = W + lam * (D.T @ D)
            z = spsolve(Z, w * y)
            w = p * (y > z) + (1 - p) * (y < z)
        return z

    def preprocess_baseline_als(self):
        """Estimate baseline with ALS and subtract it. Also offer to show the baseline."""
        try:
            lam, ok1 = QInputDialog.getDouble(self, "ALS Parametresi λ", "λ (örn: 1e5):", 1e5, 1e2, 1e9, 0)
            if not ok1:
                return
            p, ok2 = QInputDialog.getDouble(self, "Asimetri p", "p (0-1, küçük değer tepe korur):", 0.01, 0.001, 0.5, 3)
            if not ok2:
                return
            niter, ok3 = QInputDialog.getInt(self, "Iterasyon", "niter:", 10, 5, 50, 1)
            if not ok3:
                return

            if hasattr(self, "xrd_datasets") and self.xrd_datasets:
                def fn(y):
                    bg = self._baseline_als(y, lam=lam, p=p, niter=niter)
                    return y - bg
                target_idx = self._select_dataset_index()
                self._ensure_backup()
                if target_idx is None or target_idx == -1:
                    self._apply_to_all(fn)
                else:
                    d = self.xrd_datasets[target_idx]
                    y_arr = d["df"].iloc[:, 1].to_numpy()
                    bg = self._baseline_als(y_arr, lam=lam, p=p, niter=niter)
                    d["df"].iloc[:, 1] = y_arr - bg
                    self.redraw_plot()
            else:
                x = self.df.iloc[:, 0].to_numpy()
                y = self.df.iloc[:, 1].to_numpy()
                bg = self._baseline_als(y, lam=lam, p=p, niter=niter)
                self._draw_background(x, bg)
                self.df.iloc[:, 1] = y - bg
                self.update_graph_from_df()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"ALS arka plan çıkarma başarısız:\n{e}")

    # ---------- Arka plan çıkarma: Rolling minimum/median ----------
    def preprocess_baseline_rolling(self):
        """Baseline by rolling minimum (morphological)."""
        try:
            win, ok = QInputDialog.getInt(self, "Rolling Min/Median", "Pencere (noktalar):", 101, 5, 2001, 2)
            if not ok:
                return
            method, ok2 = QInputDialog.getItem(self, "Yöntem", "Seç:", ["Min", "Median"], 0, False)
            if not ok2:
                return
            half = max(1, win // 2)
            def rolling_baseline(y):
                n = len(y)
                bg = np.empty(n)
                for i in range(n):
                    a = max(0, i - half)
                    b = min(n, i + half + 1)
                    if method == "Min":
                        bg[i] = np.min(y[a:b])
                    else:
                        bg[i] = np.median(y[a:b])
                return bg
            if hasattr(self, "xrd_datasets") and self.xrd_datasets:
                def fn(y):
                    bg = rolling_baseline(y)
                    return y - bg
                target_idx = self._select_dataset_index()
                self._ensure_backup()
                if target_idx is None or target_idx == -1:
                    self._apply_to_all(fn)
                else:
                    d = self.xrd_datasets[target_idx]
                    y_arr = d["df"].iloc[:, 1].to_numpy()
                    bg = rolling_baseline(y_arr)
                    d["df"].iloc[:, 1] = y_arr - bg
                    self.redraw_plot()
            else:
                x = self.df.iloc[:, 0].to_numpy()
                y = self.df.iloc[:, 1].to_numpy()
                bg = rolling_baseline(y)
                self._draw_background(x, bg)
                self.df.iloc[:, 1] = y - bg
                self.update_graph_from_df()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Rolling arka plan çıkarma başarısız:\n{e}")

    def preprocess_reset(self):
        """Revert to original data (and clear background curve)."""
        if hasattr(self, "_bg_line") and self._bg_line is not None:
            try:
                self._bg_line.remove()
            except Exception:
                pass
            self._bg_line = None
        if hasattr(self, "_orig_df") and self._orig_df is not None:
            self.df = self._orig_df.copy()
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            for d in self.xrd_datasets:
                if "orig_df" in d and d["orig_df"] is not None:
                    d["df"] = d["orig_df"].copy()
            self.redraw_plot()
        else:
            self.update_graph_from_df()

    def interpret_trend_ai(self):
        import numpy as np
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score

        def analyze_trend(x, y, label):
            x_vals = x.reshape(-1, 1)
            model = LinearRegression()
            model.fit(x_vals, y)
            predicted = model.predict(x_vals)
            slope = model.coef_[0]
            r2 = r2_score(y, predicted)

            if abs(slope) < 0.01:
                yorum = f"{label} zamanla sabit kalmıştır."
            elif slope > 0:
                yorum = f"{label} zamanla artmaktadır."
            else:
                yorum = f"{label} zamanla azalmaktadır."

            yorum += f"\n  - Ortalama eğim: {slope:.4f}\n  - R² değeri: {r2:.3f}"
            return yorum

        yorum_temp = analyze_trend(self.df['Time'].values, self.df['Temperature'].values, "Sıcaklık")
        yorum_disp = analyze_trend(self.df['Time'].values, self.df['Displacement'].values, "Deplasman")

        QMessageBox.information(self, "Trend Yorumlama", yorum_temp + "\n\n" + yorum_disp)

# --- Multi-series plotting from Excel ---
    def plot_multi_series_from_excel(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Excel Dosyası Seç (Çoklu Seri)", "", "Excel Files (*.xlsx *.xls)")
        if not filename:
            return

        try:
            multi_df = pd.read_excel(filename, header=0)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel okunamadı: {e}")
            return

        if multi_df.shape[1] < 2:
            QMessageBox.warning(self, "Uyarı", "En az bir X ve bir Y serisi olmalı.")
            return

        # Drop NA values and check if X is numeric
        multi_df = multi_df.dropna()
        x = multi_df.iloc[:, 0]
        if not np.issubdtype(x.dtype, np.number):
            QMessageBox.critical(self, "Hata", "İlk sütun (X ekseni) sayısal veri içermelidir.")
            return

        self.ax1.clear()
        # Remove ax2 for multi-series plot
        # self.ax2.clear()
        self.figure.delaxes(self.ax2)
        self.ax2 = None

        import matplotlib.pyplot as plt
        colors = plt.cm.tab10.colors
        markers = ['o', 's', '^', 'v', 'D', '<', '>', 'p', '*', 'x']

        y_cols = multi_df.columns[1:]
        self.multi_series_lines = {}
        self.multi_series_x = x.values
        self.multi_series_ydata = {}

        for idx, col in enumerate(y_cols):
            color = colors[idx % len(colors)]
            marker = markers[idx % len(markers)]
            line, = self.ax1.plot(x, multi_df[col], marker=marker, linewidth=2, label=col, color=color)
            self.multi_series_lines[col] = line
            self.multi_series_ydata[col] = multi_df[col].values

        self.ax1.set_xlabel(str(multi_df.columns[0]), fontsize=14, fontweight='bold')
        self.ax1.set_ylabel("Y Değeri", fontsize=14, fontweight='bold')
        self.ax1.grid(True)
        self.legend_location = 'best'
        self.update_legend()
        # Populate combo box with series names
        self.combo_series.clear()
        self.combo_series.addItems([str(col) for col in y_cols])
        self.canvas.draw()

    def add_pin_marker(self):
        # Add a marker to the selected series at the nearest X value, with user-selected shape and color
        from PyQt5.QtWidgets import QMessageBox
        series = self.combo_series.currentText()
        if not hasattr(self, "multi_series_lines") or not self.multi_series_lines:
            QMessageBox.warning(self, "Uyarı", "Önce çoklu seri grafiği çiziniz.")
            return
        if series not in self.multi_series_lines:
            QMessageBox.warning(self, "Uyarı", "Seçili seri bulunamadı.")
            return
        try:
            x_str = self.input_pin_x.text()
            x_val = float(x_str)
        except Exception:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir X değeri giriniz.")
            return
        xdata = self.multi_series_x
        ydata = self.multi_series_ydata[series]
        # Find index of nearest X
        idx = np.abs(xdata - x_val).argmin()
        x_nearest = xdata[idx]
        y_nearest = ydata[idx]
        # Read marker style and color from combo boxes
        marker_style = self.combo_pin_shape.currentText()
        marker_color = self.combo_pin_color.currentText()
        # Draw marker with selected style and color, and store the artist
        pin_artist, = self.ax1.plot(
            x_nearest, y_nearest, marker_style,
            color=marker_color, markersize=10, label=f"{series} Pin"
        )
        self.pin_artists.append(pin_artist)
        self.canvas.draw()

    def toggle_pin_visibility(self):
        # Toggle visibility of all pin markers
        if not self.pin_artists:
            return
        new_visible = not self.pins_visible
        for artist in self.pin_artists:
            artist.set_visible(new_visible)
        self.pins_visible = new_visible
        self.canvas.draw()

    # --------- Project Save/Load utilities ----------
    def _collect_project_state(self):
        state = {}
        # Style & axes
        state["style"] = self._current_style_name()
        state["mpl_style"] = getattr(self, "current_style", self._current_style_name())
        # Font settings
        if hasattr(self, "font_combo"):
            state["font"] = self.font_combo.currentText()
        if hasattr(self, "font_size_input"):
            try:
                state["font_size"] = float(self.font_size_input.text())
            except Exception:
                state["font_size"] = None
        # rcParams (make JSON-serializable)
        rc_serializable = {}
        for k, v in plt.rcParams.items():
            try:
                json.dumps(v)
                rc_serializable[k] = v
            except TypeError:
                rc_serializable[k] = str(v)
        state["rcParams"] = rc_serializable
        if hasattr(self, "ax") and self.ax is not None:
            state["xlabel"] = self.ax.get_xlabel()
            state["ylabel"] = self.ax.get_ylabel()
            state["title"]  = self.ax.get_title()
            state["xlim"]   = list(self.ax.get_xlim())
            state["ylim"]   = list(self.ax.get_ylim())
        state["grid"] = getattr(self, "_xrd_grid_state", False)
        state["legend_location"] = getattr(self, "legend_location", "best")
        state["legend_custom_order"] = getattr(self, "legend_custom_order", None)
        # Datasets with full data (so we can resume without original files)
        datasets = []
        if hasattr(self, "xrd_datasets") and self.xrd_datasets:
            for d in self.xrd_datasets:
                df = d["df"]
                datasets.append({
                    "filename": d.get("filename"),
                    "color": d.get("color"),
                    "offset": d.get("offset", 0.0),
                    "x": df.iloc[:, 0].to_list(),
                    "y": df.iloc[:, 1].to_list()
                })
        else:
            # Single df fallback
            if hasattr(self, "df") and self.df is not None:
                datasets.append({
                    "filename": "Main",
                    "color": "#1f77b4",
                    "offset": 0.0,
                    "x": self.df.iloc[:, 0].to_list(),
                    "y": self.df.iloc[:, 1].to_list()
                })
        state["datasets"] = datasets
        return state

    def _apply_project_state(self, state):
        # Style and rcParams
        rc_params = state.get("rcParams")
        if rc_params:
            plt.rcParams.update(rc_params)
        mpl_style = state.get("mpl_style") or state.get("style")
        if mpl_style:
            try:
                plt.style.use(mpl_style)
                if hasattr(self, "theme_combo"):
                    self.theme_combo.setCurrentText(mpl_style)
            except Exception:
                pass
        # Build datasets from saved data
        self.xrd_datasets = []
        for d in state.get("datasets", []):
            x = pd.Series(d.get("x", []))
            y = pd.Series(d.get("y", []))
            df = pd.DataFrame({"x": x, "y": y})
            # Ensure two unnamed columns for consistency with the rest of the code
            df = df[["x", "y"]]
            df.columns = [0, 1]
            self.xrd_datasets.append({
                "filename": d.get("filename", "Dataset"),
                "df": df,
                "offset": d.get("offset", 0.0),
                "color": d.get("color", "#1f77b4"),
                "orig_df": df.copy(),
            })
        # Apply axes, grid, and fonts
        if hasattr(self, "ax") and self.ax is not None:
            if "xlabel" in state:
                self.ax.set_xlabel(state["xlabel"])
            if "ylabel" in state:
                self.ax.set_ylabel(state["ylabel"])
            if "title"  in state:
                self.ax.set_title(state["title"])
            if "xlim"   in state:
                self.ax.set_xlim(*state["xlim"])
            if "ylim"   in state:
                self.ax.set_ylim(*state["ylim"])
        self._xrd_grid_state = bool(state.get("grid", False))
        if hasattr(self, "ax") and self.ax is not None:
            self.ax.grid(self._xrd_grid_state)
        font = state.get("font")
        font_size = state.get("font_size")
        if font and font_size:
            self.apply_font_settings(font, font_size)
        # Legend prefs
        self.legend_location = state.get("legend_location", getattr(self, "legend_location", "best"))
        self.legend_custom_order = state.get("legend_custom_order", None)
        # Redraw
        self.redraw_plot()
        self.update_legend()

    def save_project(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Projeyi Kaydet", "", "XRD Project (*.xrdproj)")
        if not fname:
            return
        state = self._collect_project_state()
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Bilgi", "Proje kaydedildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Proje kaydedilemedi:\n{e}")

    def load_project(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Projeyi Aç", "", "XRD Project (*.xrdproj)")
        if not fname:
            return
        try:
            with open(fname, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Proje dosyası açılamadı:\n{e}")
            return
        try:
            # ensure figure/axes exist (if loading right after startup)
            if not hasattr(self, "ax") or not hasattr(self, "canvas"):
                self.plot_graph()
            self._apply_project_state(state)
            QMessageBox.information(self, "Bilgi", "Proje yüklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Proje uygulanamadı:\n{e}")

# Uygulamayı başlat
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = RenkDegistirici()
    pencere.show()
    sys.exit(app.exec_())

    def save_project(self):
        """Backward-compatible wrapper for 'Projeyi Kaydet'. Uses the existing XRD settings saver."""
        return self.save_xrd_settings()

    def load_project(self):
        """Backward-compatible wrapper for 'Projeyi Aç'. Uses the existing XRD settings loader."""
        return self.load_xrd_settings()

    def apply_theme_from_combo(self):
        """Apply the selected Matplotlib style from the combo box and refresh the plot safely."""
        try:
            style = self.theme_combo.currentText()
            if style:
                plt.style.use(style)
            # Redraw without assuming self.df exists
            self.redraw_plot()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tema uygulanamadı:\n{e}")
    def save_project(self):
        """Wrapper for backwards compatibility. Calls save_xrd_settings if present."""
        if hasattr(self, 'save_xrd_settings'):
            return self.save_xrd_settings()
        elif hasattr(self, 'save_preset'):
            return self.save_preset()
        else:
            QMessageBox.warning(self, "Uyarı", "Henüz kaydetme fonksiyonu tanımlı değil.")

    def load_project(self):
        """Wrapper for backwards compatibility. Calls load_xrd_settings if present."""
        if hasattr(self, 'load_xrd_settings'):
            return self.load_xrd_settings()
        else:
            QMessageBox.warning(self, "Uyarı", "Henüz açma fonksiyonu tanımlı değil.")