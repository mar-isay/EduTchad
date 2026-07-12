# backend/main.py dosyasında bu satırları geçici olarak kapat:

# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
# genai.configure(api_key=GEMINI_API_KEY)
# ai_model = genai.GenerativeModel('gemini-2.5-flash')

# backend/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
import datetime
import os
import google.generativeai as genai

import models, schemas
from database import engine, get_db
from fastapi.staticfiles import StaticFiles
import shutil

# Dökümanların yükleneceği klasörü otomatik oluştur
UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Yüklenen dosyaları dışarıya statik olarak aç (Frontend erişebilsin diye)
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.5-flash')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "SUPER_SECRET_KEY_EDUTCHAD"
ALGORITHM = "HS256"

app = FastAPI(title="EduTchad API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@app.get("/")
def read_root():
    return {"status": "success", "message": "EduTchad API Çalışıyor, Gemini Hazır!"}

@app.post("/api/register", response_model=schemas.Token)
def register_user(user: schemas.UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        # DİNAMİK DİL DESTEĞİ İÇİN HATA KODU FIRLATIYORUZ
        raise HTTPException(status_code=400, detail="EMAIL_ALREADY_EXISTS")
    
    hashed_pwd = get_password_hash(user.password)
    new_user = models.User(
        fullname=user.fullname,
        email=user.email,
        hashed_password=hashed_pwd,
        university=user.university  
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.email, "id": new_user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/login", response_model=schemas.Token)
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        # DİNAMİK DİL DESTEĞİ İÇİN HATA KODU FIRLATIYORUZ
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS"
        )
    
    access_token = create_access_token(data={"sub": db_user.email, "id": db_user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/ai/chat")
async def ai_chat(prompt: str, lang: str = "tr"):
    try:
        system_instruction = f"Sen EduTchad platformunun akademik asistanısın. Lütfen şu dilde cevap ver: {lang}. Yanıtların akademik, destekleyici ve net olsun."
        response = ai_model.generate_content(f"{system_instruction}\n\nÖğrenci Sorusu: {prompt}")
        return {"status": "success", "response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail="UNKNOWN_ERROR")

@app.post("/api/ai/analyze-text")
async def analyze_text(text_content: str, mode: str = "summary", lang: str = "tr"):
    try:
        if mode == "summary":
            prompt = f"Aşağıdaki akademik metni saniyeler içinde özetle ve önemli noktaları listele. Dil: {lang}\n\nMetin:\n{text_content}"
        else:
            prompt = f"Aşağıdaki ödev/makale metnini akademik standartlara göre optimize et, yazım hatalarını düzelt. Dil: {lang}\n\nMetin:\n{text_content}"
            
        response = ai_model.generate_content(prompt)
        return {"status": "success", "result": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail="UNKNOWN_ERROR")

# --- DÖKÜMAN YÜKLEME VE PDF ANALİZ ENDPOINT'LERİ ---

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Öğrencilerin ders notlarını ve PDF'lerini sunucuya yüklemesini sağlar.
    """
    try:
        # Dosya adını güvenli hale getir ve kayıt yolunu belirle
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        
        # Dosyayı sunucuya yaz
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "status": "success",
            "filename": file.filename,
            "file_url": f"http://127.0.0.1:8000/static/{file.filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="UPLOAD_FAILED")

@app.post("/api/ai/analyze-pdf")
async def analyze_pdf(filename: str, lang: str = "tr"):
    """
    Yüklenen PDF dosyasını Gemini API kullanarak saniyeler içinde analiz eder ve özetler.
    """
    file_location = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
        
    try:
        # Gerçek uygulamada burada bir PDF Okuyucu (PyPDF2 örn.) ile metin çekilir.
        # Hızlı prototip ve Gemini kalitesi için dosyayı simüle edip Gemini'ye yönlendiriyoruz.
        with open(file_location, "rb") as f:
            # Basit metin dosyaları veya döküman okuma simülasyonu
            file_content = f.read().decode('utf-8', errors='ignore')[:4000] # İlk 4000 karakteri analiz etmesi için sınırlandırdık
            
        prompt = f"Lütfen aşağıdaki ders notunu/akademik dökümanı saniyeler içinde analiz et, ana hatlarını çıkar ve özetle. Lütfen şu dilde yanıt ver: {lang}\n\nİçerik:\n{file_content}"
        response = ai_model.generate_content(prompt)
        
        return {"status": "success", "summary": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail="AI_ANALYSIS_FAILED")