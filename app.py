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
        
        # Dosya yoksa veya boşsa
        if response.status_code == 404 or not response.text.strip():
            return pd.DataFrame(columns=["Kitap Adı", "Yazar"])

        response.raise_for_status()
        
        # Veriyi okurken hata toleransı ekleyelim
        try:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
            # Sütun kontrolü (Eski dosya kalıntılarını temizler)
            if len(df.columns) >= 2:
                df = df.iloc[:, :2]
                df.columns = ["Kitap Adı", "Yazar"]
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
    """AI Sadece Kitap ve Yazar Okur - GÜÇLENDİRİLMİŞ VERSİYON"""
    
    # Görsel Optimizasyonu
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
            
            # --- TEMİZLİK VE AYRIŞTIRMA (PARSING) ---
            # AI'nın verdiği cevabı temizle (Markdown tırnakları vs.)
            text = text.replace("```csv", "").replace("```", "").strip()
            
            data = []
            # Satır satır oku (AI tek satır verirse diye noktalı virgül sayısına da bakabiliriz ama şimdilik split yeter)
            lines = text.split('\n')
            
            for line in lines:
                parts = line.split(';')
                if len(parts) >= 2:
                    # Sadece ilk 2 parçayı al (Kitap ve Yazar)
                    kitap = parts[0].strip()
                    yazar = parts[1].strip()
                    if kitap and yazar: # Boş değilse ekle
                        data.append({"Kitap Adı": kitap, "Yazar": yazar})
            
            if not data:
                st.warning(f"AI metin döndürdü ama format anlaşılamadı. Ham veri: {text}")
                return None
                
            return pd.DataFrame(data)
            
    except Exception as e:
        st.error(f"AI Hatası: {e}")
        return None

# --- ARAYÜZ ---

tab1, tab2 = st.tabs(["🔍 Kitap Ara", "➕ Kitap Ekle"])

with tab1:
    df = veriyi_getir()
    st.caption(f"Toplam {len(df)} kitap listelendi.")
    
    arama = st.text_input("Kitap Ara", placeholder="Kitap adı veya yazar...")
    if arama:
        sonuc = df[df.apply(lambda row: row.astype(str).str.contains(arama, case=False).any(), axis=1)]
        st.dataframe(sonuc, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    mode = st.radio("Ekleme Yöntemi", ["Fotoğrafla Tara", "Elle Ekle"])
    
    if mode == "Fotoğrafla Tara":
        uploaded_file = st.file_uploader("Raf Fotoğrafı", type=["jpg", "png", "jpeg"])
        
        if uploaded_file and st.button("Tara ve Kaydet"):
            image = Image.open(uploaded_file)
            st.image(image, caption='Analiz Ediliyor...', width=300)
            
            yeni_kitaplar_df = fotograftan_kitaplari_bul(image)
            
            if yeni_kitaplar_df is not None and not yeni_kitaplar_df.empty:
                st.success(f"{len(yeni_kitaplar_df)} kitap bulundu:")
                st.dataframe(yeni_kitaplar_df, hide_index=True)
                
                # Kayıt
                df_mevcut = veriyi_getir()
                df_son = pd.concat([df_mevcut, yeni_kitaplar_df], ignore_index=True)
                
                if veriyi_kaydet(df_son):
                    st.balloons()
                    st.success("✅ Veritabanına başarıyla kaydedildi!")
                else:
                    st.error("❌ Kaydedilemedi! Lütfen Keenetic WebDAV 'Yazma' iznini kontrol et.")

    else:
        col1, col2 = st.columns(2)
        with col1: ad = st.text_input("Kitap Adı")
        with col2: yazar = st.text_input("Yazar")
        
        if st.button("Listeye Ekle"):
            if ad and yazar:
                df_mevcut = veriyi_getir()
                yeni = pd.DataFrame([{"Kitap Adı": ad, "Yazar": yazar}])
                df_son = pd.concat([df_mevcut, yeni], ignore_index=True)
                
                if veriyi_kaydet(df_son):
                    st.success(f"✅ {ad} eklendi!")
                    st.rerun()
