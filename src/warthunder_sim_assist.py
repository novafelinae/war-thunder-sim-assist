"""
War Thunder Sim Assist
----------------------
Simülatör maçları için periyot kronometresi.

- Doğduğun anda sayaç OTOMATİK başlar (War Thunder'ın yerel telemetri
  arayüzü localhost:8111 okunur; oyun belleğine/dosyalarına dokunulmaz).
- Gösterim (dijital saat rakamlarıyla):  PERİYOT / DD:SS    örnek:  1 / 00:25
  Periyot her 15 dakikada (ayarlanabilir) bir artar ve dakika:saniye
  sayacı sıfırdan başlar.
- Periyotlar maç boyunca korunur: ilk periyot bitmeden ölüp tekrar
  doğsan bile bir sonraki periyottan (2 / 00:00) devam edilir.
  Maçtan çıkıp hangara dönünce ya da yeni bir maça girince 1'den başlar.
- Öldüğünde sayaç donar ve süre rakamları KIRMIZI olur.
- Pencere kenarlıksızdır ve varsayılan olarak arka planı şeffaftır.
  Rakamlara basılı tutup ekranda istediğin yere sürükle; konum hatırlanır.
- Sağ tık menüsü: Başlat/Duraklat, Sıfırla, Periyot +1/-1, Otomatik başlat,
  Boyut, Periyot süresi, Genel şeffaflık, Arka plan, Veri klasörü, Kapat.
- Çift tık: manuel başlat / duraklat (telemetri çalışmazsa yedek yol).

Kaynaktan çalıştırma:  python warthunder_sim_assist.py   (Python 3.8+, ek paket yok)
Windows uygulaması:    build.bat  ya da GitHub Actions ile derlenir (README'ye bak).

Not: Oyunu "Pencere" veya "Kenarlıksız pencere" modunda çalıştır.
Gerçek "Tam ekran" modunda hiçbir masaüstü penceresi oyunun üstünde
görünmez.

Resmî olmayan bir hayran aracıdır; Gaijin Entertainment ile bağlantılı değildir.
"""

import json
import os
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import messagebox

SURUM = "1.0.0"
UYGULAMA_ADI = "War Thunder Sim Assist"
MUTEX_ADI = "WarThunderSimAssist_SingleInstance"   # installer.iss içindeki AppMutex ile aynı
TELEMETRI_TABAN = "http://localhost:8111"


def veri_klasoru() -> str:
    """Ayar ve günlük dosyalarının klasörü (Windows'ta %LOCALAPPDATA%\\WarThunderSimAssist)."""
    taban = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    klasor = os.path.join(taban, "WarThunderSimAssist")
    try:
        os.makedirs(klasor, exist_ok=True)
        return klasor
    except Exception:
        return os.path.expanduser("~")


VERI_KLASORU = veri_klasoru()
AYAR_DOSYASI = os.path.join(VERI_KLASORU, "ayarlar.json")
VARSAYILAN_AYAR = {"x": 40, "y": 40, "aralik_dk": 15, "oto": True,
                   "alpha": 0.9, "boyut": "Orta", "arka_plan": "Şeffaf"}

OLUM_BEKLEME_SN = 1.0       # araç verisi bu kadar süre yoksa öldük say
MAC_BITTI_BEKLEME_SN = 10   # harita/oyun verisi bu kadar süre yoksa maç bitti say
ZAMAN_ASIMI_SN = 300        # yedek: bu kadar süre hiç araç yoksa maç bitti say

# Rakam yüksekliği (piksel). Menüdeki "Boyut" seçenekleri.
BOYUTLAR = {"Küçük": 28, "Orta": 44, "Büyük": 64, "Çok büyük": 92}

BG = "#14181c"
ANAHTAR_RENK = "#010101"    # "Şeffaf" arka planda bu renk tamamen görünmez olur
FG = "#e6edf3"
RENK_PERIYOT = "#58a6ff"
RENK_SOLUK = "#6e7681"
RENK_OLU = "#ff3b30"        # öldüğünde süre rakamları
HAYALET = "#232a31"         # yanmayan (sönük) segmentler
RENK_NOKTA_YESIL = "#3fb950"
RENK_NOKTA_SARI = "#d29922"

# 7 segmentli rakam haritası:  a=üst, b=sağ üst, c=sağ alt, d=alt,
# e=sol alt, f=sol üst, g=orta
SEGMENT_HARITASI = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
    "-": "g",
}


def periyot_hesapla(gecen_sn: float, aralik_sn: int, baz: int = 1):
    """(periyot_no, periyot_ici_dakika, periyot_ici_saniye) döndürür.

    baz: bu hayatın başladığı periyot numarası (yeniden doğuşlarda artar).
    """
    gecen = int(gecen_sn)
    periyot = baz + gecen // aralik_sn
    ici = gecen % aralik_sn
    return periyot, ici // 60, ici % 60


def segment_noktalari(ad, x, y, W, H, T):
    """Bir 7 segmentli rakamın tek bir segmentinin köşe noktaları (düz liste)."""
    bosluk = max(1.0, T * 0.10)
    yarim = T / 2

    def yatay(yc):
        xl = x + yarim + bosluk
        xr = x + W - yarim - bosluk
        return [xl, yc, xl + yarim, yc - yarim, xr - yarim, yc - yarim,
                xr, yc, xr - yarim, yc + yarim, xl + yarim, yc + yarim]

    def dikey(xc, yt, yb):
        return [xc, yt, xc + yarim, yt + yarim, xc + yarim, yb - yarim,
                xc, yb, xc - yarim, yb - yarim, xc - yarim, yt + yarim]

    ust, orta, alt = y + yarim, y + H / 2, y + H - yarim
    sol, sag = x + yarim, x + W - yarim
    if ad == "a":
        return yatay(ust)
    if ad == "g":
        return yatay(orta)
    if ad == "d":
        return yatay(alt)
    if ad == "f":
        return dikey(sol, ust + bosluk, orta - bosluk)
    if ad == "b":
        return dikey(sag, ust + bosluk, orta - bosluk)
    if ad == "e":
        return dikey(sol, orta + bosluk, alt - bosluk)
    return dikey(sag, orta + bosluk, alt - bosluk)  # "c"


def ayar_yukle() -> dict:
    ayar = dict(VARSAYILAN_AYAR)
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            ayar.update(json.load(f))
    except Exception:
        pass
    if ayar.get("boyut") not in BOYUTLAR:
        ayar["boyut"] = VARSAYILAN_AYAR["boyut"]
    if ayar.get("arka_plan") not in ("Şeffaf", "Koyu"):
        ayar["arka_plan"] = VARSAYILAN_AYAR["arka_plan"]
    return ayar


def ayar_kaydet(ayar: dict):
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ayar, f)
    except Exception:
        pass


class SimAssist:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.ayar = ayar_yukle()
        self.H = BOYUTLAR[self.ayar["boyut"]]
        self._son_anahtar = None

        # Sayaç durumu
        self.calisiyor = False
        self.baslangic = 0.0
        self.biriken = 0.0
        self.otomatik_basladi = False  # sayaç telemetri ile mi başladı?
        self.baz_periyot = 1           # bu hayatın başladığı periyot
        self.mac_icinde = False        # maç oturumu devam ediyor mu?
        self.son_harita_gen = None     # son doğuştaki harita kimliği

        # Telemetri durumu (thread'ler arası basit bayraklar)
        self.tele_ulasilabilir = False
        self.tele_gecerli = False          # araçtayız (hayattayız)
        self.tele_harita_gecerli = False   # maçın haritası açık
        self.tele_harita_gen = None
        self.tele_gecerli_onceki = False
        self.tele_son_gecerli = 0.0
        self.tele_son_harita = 0.0
        self.tele_son_ulasilabilir = 0.0
        self.tele_aktif = True

        self._pencere_kur()
        self._arayuz_kur()
        self._zemin_uygula()
        self._menu_kur()

        threading.Thread(target=self._telemetri_dongusu, daemon=True).start()
        self._tick()

    # ------------------------------------------------------- Pencere
    def _pencere_kur(self):
        r = self.root
        r.overrideredirect(True)           # kenarlıksız
        r.attributes("-topmost", True)     # hep üstte
        try:
            r.attributes("-alpha", float(self.ayar["alpha"]))
        except tk.TclError:
            pass
        r.configure(bg=BG)
        r.geometry(f"+{int(self.ayar['x'])}+{int(self.ayar['y'])}")

    seffaf_aktif = False

    def _zemin_uygula(self):
        """Arka planı ayara göre ayarlar: 'Şeffaf' ise yalnızca rakamlar görünür
        (Windows'ta -transparentcolor); desteklenmezse koyu zemine döner."""
        aktif = False
        if self.ayar.get("arka_plan") == "Şeffaf":
            try:
                self.root.attributes("-transparentcolor", ANAHTAR_RENK)
                aktif = True
            except tk.TclError:
                aktif = False
        if not aktif:
            try:
                self.root.attributes("-transparentcolor", "")
            except tk.TclError:
                pass
        self.seffaf_aktif = aktif
        zemin = ANAHTAR_RENK if aktif else BG
        self.root.configure(bg=zemin)
        self.kap.configure(bg=zemin, highlightthickness=0 if aktif else 1)
        self.canvas.configure(bg=zemin)
        self._son_anahtar = None   # bir sonraki turda yeniden çiz

    def _arayuz_kur(self):
        kap = tk.Frame(self.root, bg=BG, highlightthickness=1,
                       highlightbackground="#30363d")
        kap.pack()
        self.kap = kap

        self.canvas = tk.Canvas(kap, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack()

        # Sürükleme + çift tık + sağ tık
        for w in (self.root, kap, self.canvas):
            w.bind("<ButtonPress-1>", self._surukle_basla)
            w.bind("<B1-Motion>", self._surukle)
            w.bind("<ButtonRelease-1>", self._surukle_bitti)
            w.bind("<Double-Button-1>", lambda e: self._bosluk())
            w.bind("<Button-3>", self._menu_goster)

    def _menu_kur(self):
        m = tk.Menu(self.root, tearoff=0)
        self.menu = m

        m.add_command(label="Başlat / Duraklat", command=self._bosluk)
        m.add_command(label="Sıfırla", command=self.sifirla)
        m.add_command(label="Periyot +1", command=lambda: self.periyot_ayarla(1))
        m.add_command(label="Periyot -1", command=lambda: self.periyot_ayarla(-1))
        m.add_separator()

        self.oto_var = tk.BooleanVar(value=bool(self.ayar["oto"]))
        m.add_checkbutton(label="Doğuşta otomatik başlat", variable=self.oto_var,
                          command=self._oto_degisti)

        self.boyut_var = tk.StringVar(value=self.ayar["boyut"])
        boyut_menu = tk.Menu(m, tearoff=0)
        for ad in BOYUTLAR:
            boyut_menu.add_radiobutton(label=ad, value=ad,
                                       variable=self.boyut_var,
                                       command=self._boyut_degisti)
        m.add_cascade(label="Boyut", menu=boyut_menu)

        self.aralik_var = tk.IntVar(value=int(self.ayar["aralik_dk"]))
        aralik_menu = tk.Menu(m, tearoff=0)
        for dk in (5, 10, 15, 20, 30):
            aralik_menu.add_radiobutton(label=f"{dk} dakika", value=dk,
                                        variable=self.aralik_var,
                                        command=self._aralik_degisti)
        m.add_cascade(label="Periyot süresi", menu=aralik_menu)

        self.alpha_var = tk.DoubleVar(value=float(self.ayar["alpha"]))
        alpha_menu = tk.Menu(m, tearoff=0)
        for yuzde in (100, 90, 70, 50):
            alpha_menu.add_radiobutton(label=f"%{yuzde}", value=yuzde / 100,
                                       variable=self.alpha_var,
                                       command=self._alpha_degisti)
        m.add_cascade(label="Genel şeffaflık", menu=alpha_menu)

        self.zemin_var = tk.StringVar(value=self.ayar["arka_plan"])
        zemin_menu = tk.Menu(m, tearoff=0)
        for ad in ("Şeffaf", "Koyu"):
            zemin_menu.add_radiobutton(label=ad, value=ad, variable=self.zemin_var,
                                       command=self._zemin_degisti)
        m.add_cascade(label="Arka plan", menu=zemin_menu)

        m.add_separator()
        m.add_command(label="Veri klasörünü aç", command=self.veri_klasorunu_ac)
        m.add_command(label="Telemetri bilgisini kaydet (sorun giderme)",
                      command=self.telemetri_kaydet)
        m.add_command(label="Hakkında", command=self.hakkinda)
        m.add_command(label="Kapat", command=self._kapat)

    def veri_klasorunu_ac(self):
        try:
            if hasattr(os, "startfile"):
                os.startfile(VERI_KLASORU)
            else:
                messagebox.showinfo("Veri klasörü", VERI_KLASORU, parent=self.root)
        except Exception as e:
            messagebox.showerror("Veri klasörü", f"Açılamadı: {e}", parent=self.root)

    def hakkinda(self):
        messagebox.showinfo(
            "Hakkında",
            f"{UYGULAMA_ADI} v{SURUM}\n\n"
            "Simülatör maçları için periyot kronometresi.\n"
            "Yalnızca oyunun yerel telemetri arayüzünü (localhost:8111) okur; "
            "oyun belleğine veya dosyalarına dokunmaz ve hiçbir veri göndermez.\n\n"
            "Resmî olmayan bir hayran aracıdır; Gaijin Entertainment ile "
            "bağlantılı değildir.\n\n"
            f"Ayar ve günlük klasörü:\n{VERI_KLASORU}",
            parent=self.root)

    def _menu_goster(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ------------------------------------------------------ Sürükleme
    def _surukle_basla(self, event):
        self._dx = event.x_root - self.root.winfo_x()
        self._dy = event.y_root - self.root.winfo_y()

    def _surukle(self, event):
        x = event.x_root - self._dx
        y = event.y_root - self._dy
        self.root.geometry(f"+{x}+{y}")

    def _surukle_bitti(self, event):
        self.ayar["x"] = self.root.winfo_x()
        self.ayar["y"] = self.root.winfo_y()
        ayar_kaydet(self.ayar)

    # ------------------------------------------------------ Ayarlar
    def _oto_degisti(self):
        self.ayar["oto"] = bool(self.oto_var.get())
        ayar_kaydet(self.ayar)

    def _boyut_degisti(self):
        ad = self.boyut_var.get()
        if ad in BOYUTLAR:
            self.ayar["boyut"] = ad
            self.H = BOYUTLAR[ad]
            self._son_anahtar = None   # bir sonraki turda yeniden çiz
            ayar_kaydet(self.ayar)

    def _aralik_degisti(self):
        self.ayar["aralik_dk"] = int(self.aralik_var.get())
        ayar_kaydet(self.ayar)

    def _zemin_degisti(self):
        ad = self.zemin_var.get()
        if ad in ("Şeffaf", "Koyu"):
            self.ayar["arka_plan"] = ad
            self._zemin_uygula()
            ayar_kaydet(self.ayar)

    def _alpha_degisti(self):
        self.ayar["alpha"] = float(self.alpha_var.get())
        try:
            self.root.attributes("-alpha", self.ayar["alpha"])
        except tk.TclError:
            pass
        ayar_kaydet(self.ayar)

    # ---------------------------------------------------- Kontroller
    def gecen(self) -> float:
        """Bu hayatın başından beri geçen süre (sn)."""
        if self.calisiyor:
            return self.biriken + (time.monotonic() - self.baslangic)
        return self.biriken

    def mevcut_periyot(self) -> int:
        aralik_sn = int(self.ayar["aralik_dk"]) * 60
        return periyot_hesapla(self.gecen(), aralik_sn, self.baz_periyot)[0]

    def baslat(self, otomatik=False):
        if not self.calisiyor:
            self.baslangic = time.monotonic()
            self.calisiyor = True
            self.otomatik_basladi = otomatik

    def duraklat(self):
        if self.calisiyor:
            self.biriken = self.gecen()
            self.calisiyor = False

    def sifirla(self):
        """Her şeyi başa alır: periyot 1'e döner, maç oturumu biter."""
        self.calisiyor = False
        self.biriken = 0.0
        self.otomatik_basladi = False
        self.baz_periyot = 1
        self.mac_icinde = False
        self.son_harita_gen = None

    def periyot_ayarla(self, fark: int):
        """Elle düzeltme: mevcut hayatın periyot numarasını değiştirir."""
        self.baz_periyot = max(1, self.baz_periyot + fark)

    def _bosluk(self):
        if self.calisiyor:
            self.duraklat()
        else:
            self.baslat(otomatik=False)

    # ------------------------------------------------------- Çizim
    def _rakam_ciz(self, x, y, ch, yanik, W, H, T):
        yanan = SEGMENT_HARITASI.get(ch, "")
        for ad in "abcdefg":
            if ad in yanan:
                renk = yanik
            elif self.seffaf_aktif:
                continue    # şeffaf zeminde sönük segment çizme
            else:
                renk = HAYALET
            self.canvas.create_polygon(
                segment_noktalari(ad, x, y, W, H, T), fill=renk, outline="")

    def _ciz(self, periyot_metin, periyot_renk, sure, sure_renk, nokta_renk):
        """Tüm göstergeyi (nokta, periyot, /, DD:SS) tuvale çizer."""
        H = float(self.H)
        W = H * 0.56            # rakam genişliği
        T = H * 0.15            # segment kalınlığı
        pad = H * 0.22
        r = max(3.0, H * 0.07)  # durum noktası yarıçapı
        rakam_arasi = H * 0.12
        nokta_bosluk = H * 0.26
        ayrac_bosluk = H * 0.16
        egik_g = H * 0.30
        iki_nokta_g = H * 0.32

        parcalar = [("nokta", nokta_renk, 2 * r), ("bosluk", None, nokta_bosluk)]

        def grup(metin, renk):
            for i, ch in enumerate(metin):
                if i:
                    parcalar.append(("bosluk", None, rakam_arasi))
                parcalar.append(("rakam", (ch, renk), W))

        grup(periyot_metin, periyot_renk)
        parcalar += [("bosluk", None, ayrac_bosluk),
                     ("egik", RENK_SOLUK, egik_g),
                     ("bosluk", None, ayrac_bosluk)]
        grup(sure[:2], sure_renk)
        parcalar.append(("ikinokta", sure_renk, iki_nokta_g))
        grup(sure[2:], sure_renk)

        toplam = sum(p[2] for p in parcalar) + 2 * pad
        self.canvas.delete("all")
        self.canvas.config(width=int(round(toplam)), height=int(round(H + 2 * pad)))

        x = pad
        y = pad
        for tur, veri, genislik in parcalar:
            if tur == "nokta":
                self.canvas.create_oval(x, y + H / 2 - r, x + 2 * r, y + H / 2 + r,
                                        fill=veri, outline="")
            elif tur == "rakam":
                self._rakam_ciz(x, y, veri[0], veri[1], W, H, T)
            elif tur == "egik":
                k = T * 0.8
                self.canvas.create_polygon(
                    [x, y + H, x + k, y + H, x + genislik, y, x + genislik - k, y],
                    fill=veri, outline="")
            elif tur == "ikinokta":
                cx = x + genislik / 2
                for oran in (0.30, 0.70):
                    cy = y + H * oran
                    self.canvas.create_rectangle(
                        cx - T / 2, cy - T / 2, cx + T / 2, cy + T / 2,
                        fill=veri, outline="")
            x += genislik

    # ------------------------------------------------------- Döngü
    def _tick(self):
        gecen = self.gecen()
        aralik_sn = int(self.ayar["aralik_dk"]) * 60

        if self.calisiyor or self.biriken > 0 or self.mac_icinde:
            periyot, dk, sn = periyot_hesapla(gecen, aralik_sn, self.baz_periyot)
            periyot_metin = str(periyot)
            periyot_renk = RENK_PERIYOT
            sure = f"{dk:02d}{sn:02d}"
            sure_renk = FG if self.calisiyor else RENK_OLU
        else:
            periyot_metin = "-"
            periyot_renk = RENK_SOLUK
            sure = "0000"
            sure_renk = RENK_SOLUK

        # Durum noktası: yeşil = hayattayız, sarı = oyun açık ama araç yok
        # (ölü / hangar), gri = telemetriye ulaşılamıyor
        if self.tele_gecerli:
            nokta_renk = RENK_NOKTA_YESIL
        elif self.tele_ulasilabilir:
            nokta_renk = RENK_NOKTA_SARI
        else:
            nokta_renk = RENK_SOLUK

        anahtar = (periyot_metin, periyot_renk, sure, sure_renk, nokta_renk, self.H)
        if anahtar != self._son_anahtar:
            self._son_anahtar = anahtar
            self._ciz(periyot_metin, periyot_renk, sure, sure_renk, nokta_renk)

        self._otomatik_kontrol()

        # Oyun penceresi öne çıkarsa tekrar en üste al
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.root.after(100, self._tick)

    # --------------------------------------------------- Telemetri
    def _http_json(self, yol, zaman_asimi=0.7):
        with urllib.request.urlopen(TELEMETRI_TABAN + yol, timeout=zaman_asimi) as r:
            return json.loads(r.read().decode("utf-8"))

    def _oyuncu_haritada(self) -> bool:
        """Hayatta mıyız? Haritadaki nesneler arasında oyuncu ikonu var mı?
        (Hangarda/menüde ve ölüyken oyuncu ikonu yoktur.)"""
        try:
            nesneler = self._http_json("/map_obj.json")
        except Exception:
            return False
        if isinstance(nesneler, list):
            for n in nesneler:
                if isinstance(n, dict) and str(n.get("icon", "")).lower() == "player":
                    return True
        return False

    _gunluk_kilit = threading.Lock()
    BASLA_MARKA = "=== OTOMATİK BAŞLANGIÇ"
    BASLA_KAYIT_SAYISI = 15

    def _gunluk_yolu(self, ad):
        """Günlük dosyası için yazılabilir bir yol bulur (veri klasörü, olmazsa ev klasörü)."""
        for klasor in (VERI_KLASORU, os.path.expanduser("~")):
            yol = os.path.join(klasor, ad)
            try:
                with open(yol, "a", encoding="utf-8"):
                    pass
                return yol
            except Exception:
                continue
        return None

    def _map_obj_ozet(self) -> str:
        """Haritadaki nesnelerin kısa özeti (ikon türleri ve oyuncu kaydı)."""
        try:
            nesneler = self._http_json("/map_obj.json", 1.0)
        except Exception as e:
            return f"HATA: {e}"
        if not isinstance(nesneler, list):
            return f"liste değil: {str(nesneler)[:200]}"
        sayac = {}
        oyuncu = []
        for n in nesneler:
            if not isinstance(n, dict):
                continue
            ikon = str(n.get("icon", "?"))
            sayac[ikon] = sayac.get(ikon, 0) + 1
            if ikon.lower() == "player":
                oyuncu.append(n)
        return f"toplam={len(nesneler)} ikonlar={sayac} oyuncu={json.dumps(oyuncu)[:300]}"

    def _basla_kaydi(self, yeni_mac, gen, baz):
        """Sorun giderme: her otomatik başlangıçta oyunun o anki ham verisini
        günlüğe ekler (son 15 kayıt tutulur). Arka planda çalışır."""
        try:
            satirlar = [f"{self.BASLA_MARKA} {time.strftime('%Y-%m-%d %H:%M:%S')}"
                        f" | yeni_mac={yeni_mac} | map_generation={gen} | periyot={baz}"]
            for ep in ("/indicators", "/state", "/mission.json", "/map_info.json"):
                try:
                    with urllib.request.urlopen(TELEMETRI_TABAN + ep, timeout=1.5) as r:
                        metin = r.read().decode("utf-8", "replace")
                except Exception as e:
                    metin = f"HATA: {e}"
                satirlar.append(f"--- {ep} ---\n{metin[:600]}")
            satirlar.append("--- /map_obj.json (özet) ---\n" + self._map_obj_ozet())
            yeni = "\n".join(satirlar)[len(self.BASLA_MARKA):]

            yol = self._gunluk_yolu("wt_sim_assist_basla_log.txt")
            if not yol:
                return
            with self._gunluk_kilit:
                try:
                    with open(yol, "r", encoding="utf-8") as f:
                        eski = f.read()
                except Exception:
                    eski = ""
                parcalar = eski.split(self.BASLA_MARKA)[1:] + [yeni]
                parcalar = parcalar[-self.BASLA_KAYIT_SAYISI:]
                with open(yol, "w", encoding="utf-8") as f:
                    f.write("".join(self.BASLA_MARKA + p.rstrip("\n") + "\n\n" for p in parcalar))
        except Exception:
            pass

    def telemetri_kaydet(self):
        """Sorun giderme: oyunun verdiği ham veriyi bir metin dosyasına yazar."""
        yol = os.path.join(VERI_KLASORU, "wt_telemetri_log.txt")
        satirlar = [time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"sayaç çalışıyor={self.calisiyor} | otomatik={self.otomatik_basladi}"
                    f" | maç içinde={self.mac_icinde} | periyot={self.mevcut_periyot()}"
                    f" | araç verisi geçerli={self.tele_gecerli}"
                    f" | map_generation={self.tele_harita_gen}"]
        for ep in ("/indicators", "/state", "/mission.json", "/map_info.json"):
            try:
                with urllib.request.urlopen(TELEMETRI_TABAN + ep, timeout=1.5) as r:
                    metin = r.read().decode("utf-8", "replace")
            except Exception as e:
                metin = f"HATA: {e}"
            satirlar.append(f"--- {ep} ---\n{metin[:800]}")
        satirlar.append("--- /map_obj.json (özet) ---\n" + self._map_obj_ozet())
        try:
            with open(yol, "w", encoding="utf-8") as f:
                f.write("\n".join(satirlar))
            messagebox.showinfo("Telemetri", f"Kaydedildi:\n{yol}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Telemetri", f"Kaydedilemedi: {e}", parent=self.root)

    def _telemetri_dongusu(self):
        """War Thunder'ın yerel arayüzünü okur (oyuna müdahale etmez)."""
        harita_gecerli = False
        gen = None
        son_harita_bilgi = 0.0   # map_info.json en son ne zaman okundu
        son_basarili = 0.0       # oyun en son ne zaman cevap verdi
        onceki_gecerli = False

        while self.tele_aktif:
            basla = time.monotonic()
            ulasilabilir = False
            gecerli = False
            try:
                veri = self._http_json("/indicators", 0.5)
                ulasilabilir = True
                # Hangarda da "valid" doğru dönebildiği için hayatta olduğumuzu
                # haritada oyuncu ikonunun bulunmasıyla ayrıca doğrularız.
                if bool(veri.get("valid", False)):
                    gecerli = self._oyuncu_haritada()
            except Exception:
                pass

            if not ulasilabilir and basla - son_basarili < 3.0:
                # Kısa süreli kesinti (oyun takılması vb.): önceki durumu koru,
                # yoksa sayaç boş yere "öldü" sanıp periyot atlar.
                time.sleep(0.2)
                continue

            if ulasilabilir:
                son_basarili = basla
                # map_info.json (maç var mı, hangi harita) seyrek okunur; ama
                # doğuş anında hemen güncel harita kimliği gerekir.
                if (gecerli and not onceki_gecerli) or basla - son_harita_bilgi > 2.0:
                    son_harita_bilgi = basla
                    try:
                        bilgi = self._http_json("/map_info.json", 0.5)
                        if isinstance(bilgi, dict):
                            harita_gecerli = bool(bilgi.get("valid", True))
                            gen = bilgi.get("map_generation")
                        else:
                            harita_gecerli = True
                    except Exception:
                        # Bilgi alınamadı: maçta olduğumuzu varsay, yedek
                        # zaman aşımı devreye girer.
                        harita_gecerli = True
                harita_gecerli = harita_gecerli or gecerli
            else:
                harita_gecerli = False
                gen = None

            onceki_gecerli = gecerli
            # Sıra önemli: ana döngü "gecerli"yi görünce harita kimliği hazır olsun
            self.tele_harita_gen = gen
            self.tele_harita_gecerli = harita_gecerli
            self.tele_ulasilabilir = ulasilabilir
            self.tele_gecerli = gecerli

            gecen_sn = time.monotonic() - basla
            time.sleep(max(0.0, 0.2 - gecen_sn))

    # --------------------------------------------- Otomatik mantık
    def _otomatik_kontrol(self):
        simdi = time.monotonic()

        if self.tele_gecerli:
            self.tele_son_gecerli = simdi
        if self.tele_harita_gecerli:
            self.tele_son_harita = simdi
        if self.tele_ulasilabilir:
            self.tele_son_ulasilabilir = simdi

        if self.ayar["oto"]:
            if self.tele_gecerli and not self.tele_gecerli_onceki:
                # Sayaç hâlâ çalışıyorsa bu yeniden doğuş değil, kısa bir veri
                # kesintisidir (gerçek bir ölüm en az 1 sn sürer ve sayacı durdurur).
                if not (self.calisiyor and self.otomatik_basladi):
                    self._dogus()
            else:
                self._olum_ve_mac_sonu(simdi)

        self.tele_gecerli_onceki = self.tele_gecerli

    def _dogus(self):
        """Doğuş: ilk doğuşta 1. periyot, sonraki doğuşlarda bir sonraki periyot."""
        gen = self.tele_harita_gen
        yeni_mac = (
            not self.mac_icinde
            or (gen is not None and self.son_harita_gen is not None
                and gen != self.son_harita_gen)
        )
        if yeni_mac:
            self.baz_periyot = 1
        else:
            self.baz_periyot = self.mevcut_periyot() + 1

        self.biriken = 0.0
        self.calisiyor = False
        self.baslat(otomatik=True)
        self.mac_icinde = True
        self.son_harita_gen = gen
        threading.Thread(target=self._basla_kaydi,
                         args=(yeni_mac, gen, self.baz_periyot), daemon=True).start()

    def _olum_ve_mac_sonu(self, simdi):
        # Ölüm: araç verisi kesildi -> sayacı son görülen ana dondur.
        # Periyot bilgisi korunur, bir sonraki doğuşta devam edilir.
        if (self.otomatik_basladi and self.calisiyor and not self.tele_gecerli
                and simdi - self.tele_son_gecerli > OLUM_BEKLEME_SN):
            self.biriken += max(0.0, self.tele_son_gecerli - self.baslangic)
            self.calisiyor = False

        # Maç bitti (hangara dönüş / oyun kapandı): her şeyi sıfırla.
        if self.mac_icinde and not self.tele_gecerli:
            harita_yok = simdi - self.tele_son_harita > MAC_BITTI_BEKLEME_SN
            oyun_yok = simdi - self.tele_son_ulasilabilir > MAC_BITTI_BEKLEME_SN
            zaman_asimi = simdi - self.tele_son_gecerli > ZAMAN_ASIMI_SN
            if harita_yok or oyun_yok or zaman_asimi:
                self.sifirla()

    def _kapat(self):
        self.tele_aktif = False
        ayar_kaydet(self.ayar)
        self.root.destroy()


def hata_kaydet(metin):
    """Açılışta/çalışırken beklenmeyen hata olursa bir dosyaya yazar."""
    for klasor in (VERI_KLASORU, os.path.expanduser("~")):
        yol = os.path.join(klasor, "wt_sim_assist_hata.txt")
        try:
            with open(yol, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + metin)
            return yol
        except Exception:
            continue
    return None


_MUTEX_TUTAMAC = None   # süreç boyunca açık kalmalı


def tek_kopya_kilidi() -> bool:
    """Windows'ta ikinci bir kopyanın açılmasını engeller. True: devam edebilirsin."""
    global _MUTEX_TUTAMAC
    if os.name != "nt":
        return True
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        tutamac = kernel32.CreateMutexW(None, False, MUTEX_ADI)
        if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
            return False
        _MUTEX_TUTAMAC = tutamac
    except Exception:
        pass
    return True


if __name__ == "__main__":
    if not tek_kopya_kilidi():
        try:
            gizli = tk.Tk()
            gizli.withdraw()
            messagebox.showinfo(
                UYGULAMA_ADI,
                "Program zaten çalışıyor.\n\nPencere oyunun veya başka bir pencerenin "
                "arkasında ya da ekranın kenarında olabilir. Görünmüyorsa Görev "
                "Yöneticisi'nden kapatıp yeniden açın.")
        except Exception:
            pass
        raise SystemExit(0)
    try:
        kok = tk.Tk()
        SimAssist(kok)
        kok.mainloop()
    except Exception:
        import traceback
        metin = traceback.format_exc()
        yol = hata_kaydet(metin)
        try:
            gizli = tk.Tk()
            gizli.withdraw()
            messagebox.showerror(
                "War Thunder Sim Assist açılamadı",
                "Program bir hata nedeniyle açılamadı.\n\n"
                + (f"Hata ayrıntısı şu dosyaya yazıldı:\n{yol}\n\n" if yol else "")
                + metin[-600:])
        except Exception:
            pass
