import streamlit as st
import pandas as pd
import requests
import io
import google.generativeai as genai
from PIL import Image

# Sayfa Ayarları
st.set_page_config(page_title="Sade Kütüphane", page_icon="📚", layout="centered")
st.title("📚 Ev Kütüphanesi")

# --- AYARLAR ---
KEENETIC_URL = st.secrets["KEENETIC_URL"]
WEBDAV_USER = st.secrets["WEBDAV_USER"]
WEBDAV_PASS = st.secrets["WEBDAV_PASS"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# Model Ayarı
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- FONKSİYONLAR ---

def veriyi_getir():
    """Keenetic'ten veriyi çeker ve DataFrame'e çevirir"""
    try:
        response = requests.get(KEENETIC_URL, auth=(WEBDAV_USER, WEBDAV_PASS))
        
        if response.status_code == 404 or not response.text.strip():
            return pd.DataFrame(columns=["Kitap Adı", "Yazar"])

        response.raise_for_status()
        
        try:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
            if len(df.columns) >= 2:
                df = df.iloc[:, :2]
                df.columns = ["Kitap Adı", "Yazar"]
                # Veri tiplerini string yapalım ki karşılaştırma hatası olmasın
                df["Kitap Adı"] = df["Kitap Adı"].astype(str)
                df["Yazar"] = df["Yazar"].astype(str)
            else:
                df = pd.DataFrame(columns=["Kitap Adı", "Yazar"])
        except:
            df = pd.DataFrame(columns=["Kitap Adı", "Yazar"])
            
        return df

    except Exception as e:
        return pd.DataFrame(columns=["Kitap Adı", "Yazar"])

def veriyi_kaydet(df):
    """Listeyi Keenetic'e yazar"""
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, sep=';')
        csv_data = csv_buffer.getvalue().encode('utf-8')
        
        response = requests.put(KEENETIC_URL, data=csv_data, auth=(WEBDAV_USER, WEBDAV_PASS))
        return response.status_code in [200, 201, 204]
    except Exception as e:
        st.error(f"Yazma Hatası: {e}")
        return False

def fotograftan_kitaplari_bul(image):
    """AI Sadece Kitap ve Yazar Okur"""
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image.thumbnail((1024, 1024))

    prompt = """
    Bu fotoğraftaki kitapların sırtlarını oku.
    Bana SADECE bir CSV listesi ver.
    
    ÖNEMLİ KURALLAR:
    1. Her bir kitap MUTLAKA yeni bir satırda olmalı.
    2. Format: Kitap Adı;Yazar
    3. Başka hiçbir metin veya açıklama yazma.
    4. Markdown kullanma.
    
    Örnek Çıktı:
    Dune;Frank Herbert
    Nutuk;Atatürk
    1984;George Orwell
    """
    
    try:
        with st.spinner('Yapay zeka kitapları okuyor...'):
            response = model.generate_content([prompt, image])
            text = response.text
            text = text.replace("```csv", "").replace("```", "").strip()
            
            data = []
            lines = text.split('\n')
            
            for line in lines:
                parts = line.split(';')
                if len(parts) >= 2:
                    kitap = parts[0].strip()
                    yazar = parts[1].strip()
                    if kitap and yazar:
                        data.append({"Kitap Adı": kitap, "Yazar": yazar})
            
            if not data:
                return None
                
            return pd.DataFrame(data)
            
    except Exception as e:
        st.error(f"AI Hatası: {e}")
        return None

# --- ARAYÜZ ---

if 'kesfedilen_kitaplar' not in st.session_state:
    st.session_state.kesfedilen_kitaplar = None

tab1, tab2 = st.tabs(["🔍 Kitap Ara", "➕ Kitap Ekle"])

with tab1:
    df = veriyi_getir()
    st.caption(f"Toplam {len(df)} kitap listelendi.")
    
    arama = st.text_input("Kitap Ara", placeholder="Kitap adı veya yazar...")
    if arama:
        sonuc = df[df.apply(lambda row: row.astype(str).str.lower().str.contains(arama.lower(), case=False).any(), axis=1)]
        st.dataframe(sonuc, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    mode = st.radio("Ekleme Yöntemi", ["Fotoğrafla Tara", "Elle Ekle"])
    
    if mode == "Fotoğrafla Tara":
        uploaded_file = st.file_uploader("Raf Fotoğrafı", type=["jpg", "png", "jpeg"])
        
        # 1. Aşama: TARA
        if uploaded_file:
            if st.button("Fotoğrafı Tara 📸"):
                image = Image.open(uploaded_file)
                st.image(image, caption='Analiz Ediliyor...', width=300)
                st.session_state.kesfedilen_kitaplar = fotograftan_kitaplari_bul(image)

        # 2. Aşama: KONTROL VE KAYIT
        if st.session_state.kesfedilen_kitaplar is not None and not st.session_state.kesfedilen_kitaplar.empty:
            st.info("Bulunan kitapları kontrol et. Kaydet dersen sadece YENİ olanlar eklenecek.")
            
            edited_df = st.data_editor(st.session_state.kesfedilen_kitaplar, num_rows="dynamic", hide_index=True)
            
            col_kaydet, col_iptal = st.columns(2)
            
            if col_kaydet.button("✅ Akıllı Kayıt (Tekrarları Önle)", type="primary"):
                df_mevcut = veriyi_getir()
                
                # --- AKILLI DUPLICATE KONTROLÜ BAŞLANGICI ---
                
                # Mevcut kitapları karşılaştırma için küçük harfe çevirip listeye alalım
                # Set kullanarak işlemi hızlandırıyoruz
                mevcut_kitaplar_seti = set(df_mevcut["Kitap Adı"].astype(str).str.lower().str.strip())
                
                eklenecekler = []
                zaten_var = []
                
                # Kullanıcının onayladığı listeyi tek tek kontrol et
                for index, row in edited_df.iterrows():
                    kitap_adi_ham = str(row["Kitap Adı"]).strip()
                    kitap_adi_kontrol = kitap_adi_ham.lower()
                    
                    if kitap_adi_kontrol in mevcut_kitaplar_seti:
                        zaten_var.append(kitap_adi_ham)
                    else:
                        eklenecekler.append(row)
                
                # --- AKILLI DUPLICATE KONTROLÜ BİTİŞİ ---

                if eklenecekler:
                    df_yeni = pd.DataFrame(eklenecekler)
                    df_son = pd.concat([df_mevcut, df_yeni], ignore_index=True)
                    
                    if veriyi_kaydet(df_son):
                        st.balloons()
                        mesaj = f"✅ {len(df_yeni)} yeni kitap eklendi!"
                        if zaten_var:
                            mesaj += f"\n\n⚠️ Şu kitaplar zaten vardı, pas geçildi: {', '.join(zaten_var)}"
                        st.success(mesaj)
                        st.session_state.kesfedilen_kitaplar = None
                        st.rerun()
                    else:
                        st.error("Kaydedilemedi!")
                else:
                    st.warning(f"⚠️ Yeni kitap bulunamadı! Taradığın kitapların hepsi ({', '.join(zaten_var)}) zaten listede var.")
                    st.session_state.kesfedilen_kitaplar = None # Listeyi temizle ki ekran boşalsın
                    
            if col_iptal.button("❌ İptal"):
                st.session_state.kesfedilen_kitaplar = None
                st.rerun()

    else: # Elle Ekle
        col1, col2 = st.columns(2)
        with col1: ad = st.text_input("Kitap Adı")
        with col2: yazar = st.text_input("Yazar")
        
        if st.button("Listeye Ekle"):
            if ad and yazar:
                df_mevcut = veriyi_getir()
                
                # Elle eklemede de kontrol yapalım
                if df_mevcut["Kitap Adı"].astype(str).str.lower().str.strip().isin([ad.lower().strip()]).any():
                    st.error(f"Bu kitap ({ad}) zaten listede var!")
                else:
                    yeni = pd.DataFrame([{"Kitap Adı": ad, "Yazar": yazar}])
                    df_son = pd.concat([df_mevcut, yeni], ignore_index=True)
                    
                    if veriyi_kaydet(df_son):
                        st.success(f"✅ {ad} eklendi!")
                        st.rerun()
