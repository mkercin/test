import streamlit as st
import pandas as pd
import requests
import io
import google.generativeai as genai
from PIL import Image

# Sayfa Ayarları
st.set_page_config(page_title="Akıllı Kütüphanem", page_icon="📚", layout="wide")

st.title("📚 Evdeki Akıllı Kütüphanem")

# --- AYARLAR ---
KEENETIC_URL = st.secrets["KEENETIC_URL"]
WEBDAV_USER = st.secrets["WEBDAV_USER"]
WEBDAV_PASS = st.secrets["WEBDAV_PASS"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# AI Ayarı (Flash modeli görsel de okuyabilir)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- FONKSİYONLAR ---

def veriyi_getir():
    """Keenetic'ten CSV dosyasını okur"""
    try:
        response = requests.get(KEENETIC_URL, auth=(WEBDAV_USER, WEBDAV_PASS))
        response.raise_for_status()
        # Noktalı virgül ayırıcısına dikkat
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
        return df
    except Exception as e:
        # Eğer dosya yoksa boş bir DataFrame oluştur
        return pd.DataFrame(columns=["Kitap Adı", "Yazar", "Konum"])

def veriyi_kaydet(df):
    """Güncellenmiş listeyi Keenetic'e geri yazar (Overwrite)"""
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, sep=';') # Yine noktalı virgül kullanıyoruz
    csv_data = csv_buffer.getvalue().encode('utf-8')
    
    response = requests.put(KEENETIC_URL, data=csv_data, auth=(WEBDAV_USER, WEBDAV_PASS))
    return response.status_code == 200 or response.status_code == 201

def fotograftan_kitaplari_bul(image, konum):
    """Raf fotoğrafını AI'ya gönderip CSV formatında liste ister"""
    
    # --- OPTİMİZASYON BAŞLANGICI ---
    # 1. Görseli RGB formatına zorla (PNG şeffaflık sorunlarını çözer)
    if image.mode != 'RGB':
        image = image.convert('RGB')
        
    # 2. Görseli Küçült (Thumbnail)
    # Telefon fotoları 4000px olabilir, bunu 1024px'e düşürelim.
    # Bu işlem kaliteyi bozmaz ama dosya boyutunu %90 azaltır ve HIZLANDIRIR.
    image.thumbnail((1024, 1024)) 
    # --- OPTİMİZASYON BİTİŞİ ---

    prompt = """
    Bu bir kitaplık rafı fotoğrafı. Fotoğraftaki kitapların sırtlarını oku.
    Bana SADECE aşağıdaki CSV formatında bir liste ver. Başka hiçbir açıklama yazma.
    Eğer yazar okunmuyorsa 'Bilinmiyor' yaz.
    
    Format:
    Kitap Adı;Yazar;Konum
    
    Örnek Çıktı:
    Dune;Frank Herbert;Salon Raf 1
    Nutuk;Atatürk;Salon Raf 1
    """
    final_prompt = prompt.replace("Salon Raf 1", konum)
    
    try:
        with st.spinner('Yapay zeka fotoğrafı analiz ediyor (Bu 5-10 sn sürebilir)... 🧐'):
            # Streamlit hatasını önlemek için güvenli çağrı
            response = model.generate_content([final_prompt, image])
            return response.text.strip()
            
    except Exception as e:
        # Hatayı ekrana bas ki ne olduğunu görelim
        st.error(f"Bağlantı Hatası: {e}")
        return ""
# --- ARAYÜZ (UI) ---

# Yan Menü (Ekleme İşlemleri)
with st.sidebar:
    st.header("➕ Kitap Ekle")
    ekleme_modu = st.radio("Yöntem Seç:", ["Manuel Ekle", "Fotoğrafla Tara (BETA)"])
    
    if ekleme_modu == "Manuel Ekle":
        yeni_ad = st.text_input("Kitap Adı")
        yeni_yazar = st.text_input("Yazar")
        yeni_konum = st.text_input("Konum", value="Salon Kitaplık")
        
        if st.button("Listeye Ekle"):
            if yeni_ad:
                df_mevcut = veriyi_getir()
                yeni_satir = pd.DataFrame({"Kitap Adı": [yeni_ad], "Yazar": [yeni_yazar], "Konum": [yeni_konum]})
                df_yeni = pd.concat([df_mevcut, yeni_satir], ignore_index=True)
                
                if veriyi_kaydet(df_yeni):
                    st.success(f"{yeni_ad} eklendi!")
                    st.rerun() # Sayfayı yenile
                else:
                    st.error("Kaydedilemedi!")

    elif ekleme_modu == "Fotoğrafla Tara (BETA)":
        st.info("Kitaplığının bir rafını çek, gerisini AI halletsin.")
        uploaded_file = st.file_uploader("Fotoğraf Yükle", type=["jpg", "png", "jpeg"])
        raf_konumu = st.text_input("Bu raf nerede?", value="Salon Raf 1")
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption='Yüklenen Fotoğraf', use_container_width=True)
            
            if st.button("AI ile Tara ve Ekle"):
                ai_csv_text = fotograftan_kitaplari_bul(image, raf_konumu)
                
                # Gelen metni veriye çevir
                try:
                    # AI bazen Markdown ```csv ... ``` içine alır, temizleyelim
                    ai_csv_text = ai_csv_text.replace("```csv", "").replace("```", "").strip()
                    
                    # String'i DataFrame'e çevir
                    df_ai = pd.read_csv(io.StringIO(ai_csv_text), sep=';')
                    
                    st.write("Algılanan Kitaplar:")
                    st.dataframe(df_ai)
                    
                    # Onaylama
                    if not df_ai.empty:
                        df_mevcut = veriyi_getir()
                        df_son = pd.concat([df_mevcut, df_ai], ignore_index=True)
                        if veriyi_kaydet(df_son):
                            st.success(f"{len(df_ai)} kitap başarıyla eklendi! 🎉")
                        else:
                            st.error("Keenetic'e yazılamadı.")
                except Exception as e:
                    st.error(f"AI çıktısı işlenemedi: {e}\nÇıktı: {ai_csv_text}")

# Ana Ekran (Arama ve Listeleme)
df = veriyi_getir()

col1, col2 = st.columns([3, 1])
with col1:
    arama = st.text_input("🔍 Kitap Ara (Yapay Zeka Destekli)", placeholder="Örn: Tarih ile ilgili ne var?")

if arama:
    # Basit arama yerine AI araması (Önceki kodundaki mantık)
    prompt = f"Aşağıdaki kitap listesine bak ve soruyu cevapla: {arama}\n\nListe:\n{df.to_string()}"
    cevap = model.generate_content(prompt).text
    st.info(cevap)
else:
    st.write(f"Toplam Kitap: **{len(df)}**")
    st.dataframe(df, use_container_width=True)

