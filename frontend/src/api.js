// frontend/src/api.js
import axios from 'axios';

// Backend sunucumuzun çalıştığı temel adres
const API_URL = 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Kayıt Olma Fonksiyonu
export const registerUser = async (userData) => {
  try {
    const response = await api.post('/register', userData);
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || "Kayıt olurken bir hata oluştu.";
  }
};

// Giriş Yapma Fonksiyonu
export const loginUser = async (userData) => {
  try {
    const response = await api.post('/login', userData);
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || "Giriş yaparken bir hata oluştu.";
  }
};

// Yapay Zeka Sohbet Fonksiyonu
export const chatWithAI = async (prompt, lang) => {
  try {
    const response = await api.post(`/ai/chat?prompt=${encodeURIComponent(prompt)}&lang=${lang}`);
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || "Yapay zeka ile iletişim kurulamadı.";
  }
};

export default api;