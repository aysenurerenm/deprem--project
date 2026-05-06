import math
import os
import sys
import django
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

from datetime import time
from django.utils import timezone as django_tz


# ===============================
# DJANGO SETUP
# ===============================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'depremproject.settings')
django.setup()

print("Django başarıyla başlatıldı.")


# MODELLER
from anasayfa.models import ToplanmaAlanlari, Ihtiyac,DepoUrunler

def get_dqn_state_from_db():
    # Performance Optimization: select_related ile ürün tablosunu (aciliyet_skoru için) 
    # ve alanID üzerinden depo bilgilerini tek sorguda çekiyoruz.
    talepler = Ihtiyac.objects.select_related('urunID', 'alanID').filter(ihtiyacdurum='Bekliyor')
    
    state_vector = []
    processed_data = []
    current_time = django_tz.now()

    for talep in talepler:
        # 1. ACİLİYET (Urun tablosundan)
        base_urgency = float(talep.urunID.Aciliyet)
        
        # 2. AGING (YAŞLANMA) HESABI (Ihtiyac tablosundan)
        wait_delta = current_time - talep.talepZamanı
        wait_hours = max(0, wait_delta.total_seconds() / 3600)
        
        # Üstel yaşlanma katsayısı: Her saat %5 artış
        aging_factor = (1.05) ** wait_hours 

        # 3. LOJİSTİK VE DEPO KONTROLÜ (A-B-C Depo Mantığı)
        # Toplanma alanının bağlı olduğu ana depo
        ana_depo_id = talep.alanID.depoID 

        # Ürün ana depoda var mı? (DepoUrunler tablosu)
        stok_kaydi = DepoUrunler.objects.filter(depoID=ana_depo_id, urunID=talep.urunID).first()
        
        distance_penalty = 1.0 # Varsayılan: Ürün kendi deposunda (Mesafe kısa)
        
        if not stok_kaydi or stok_kaydi.urunMiktar < talep.ihtiyacmiktar:
            # Ürün ana depoda yoksa, alternatif depolara bak
            alternatif_stok = DepoUrunler.objects.filter(
                urunID=talep.urunID, 
                urunMiktar__gte=talep.ihtiyacmiktar
            ).exclude(depoID=ana_depo_id).first()
            
            if alternatif_stok:
                distance_penalty = 2.5 # Uzak depodan transfer maliyeti
            else:
                distance_penalty = 5.0 # Stok hiçbir yerde yok (Kritik)

        # 4. DINAMIK ÖNCELİK (Reward için temel değer)
        dynamic_priority = base_urgency * aging_factor

        # DQN'in sinir ağına girecek olan nümerik dizi (State)
        state_vector.append([
            base_urgency,
            float(aging_factor),
            float(talep.ihtiyacmiktar),
            float(distance_penalty)
        ])

        # Reward hesaplarken kullanacağımız detaylı sözlük
        processed_data.append({
            'id': talep.ihtiyacID,
            'priority': dynamic_priority,
            'amount': float(talep.ihtiyacmiktar),
            'distance_penalty': distance_penalty,
            'wait_hours': wait_hours
        })

    return np.array(state_vector), processed_data
def get_dqn_state_pro(current_load, truck_capacity):
    state_vector, processed_data = get_dqn_state_from_db()
    
    # Kalan kapasite oranını hesapla (0 ile 1 arasında normalize etmek eğitimi hızlandırır)
    remaining_ratio = (truck_capacity - current_load) / truck_capacity
    
    # Her bir talebin yanına tırın genel doluluk durumunu ekliyoruz
    # Yeni state yapısı: [base_urgency, aging_factor, amount, distance_penalty, remaining_ratio]
    extended_state = []
    for s in state_vector:
        extended_state.append(np.append(s, remaining_ratio))
        
    return np.array(extended_state), processed_data

class AfetLojistikEnv(gym.Env):
    def __init__(self, truck_capacity=1000):
        super(AfetLojistikEnv, self).__init__()
        
        # Veriyi çek ve state boyutunu belirle
        self.state_data, self.processed_data = get_dqn_state_from_db()
        self.num_items = len(self.processed_data)
        self.truck_capacity = truck_capacity
        
        # Aksiyon Alanı: Her bir ihtiyacı seçmek (0'dan N-1'e kadar)
        self.action_space = spaces.Discrete(self.num_items)
        
        # Gözlem Alanı: [base_urgency, aging_factor, amount, distance_penalty] matrisi
        # Basitlik adına tek bir vektör olarak düzleştiriyoruz
        self.observation_space = spaces.Box(low=0, high=np.inf, 
                                            shape=(self.num_items * 4,), 
                                            dtype=np.float32)
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Veriyi tazele
        self.state_data, self.processed_data = get_dqn_state_from_db()
        self.current_load = 0
        self.selected_indices = []
        
        observation = self.state_data.flatten().astype(np.float32)
        return observation, {}

    def step(self, action):
        # 1. Aynı ürünü tekrar seçerse ceza ver
        if action in self.selected_indices:
            return self.state_data.flatten(), -10, False, False, {"msg": "Tekrar seçim", "load": self.current_load}

        item = self.processed_data[action]
        
        # 2. Kapasite kontrolü
        if self.current_load + item['amount'] > self.truck_capacity:
            # Kapasite doldu, tırı gönderiyoruz (Bitiş)
            reward = 0 
            terminated = True
        else:
            # 3. Başarılı yükleme: Ödül hesapla
            # Reward = (Aciliyet * Aging) - (Mesafe Cezası)
           

            priority_score = math.log1p(item['priority'])  # daha stabil

# distance için nonlinear ceza (uzaklık arttıkça daha sert)
            distance_penalty = math.tanh(item['distance_penalty'] / 10)

            # amount normalize (varsayım: max ~100)
            amount_bonus = item['amount'] / 100.0

            reward = (
                3 * priority_score
                - 2.0 * distance_penalty
                + 0.8 * amount_bonus
            )
            self.current_load += item['amount']
            self.selected_indices.append(action)
            # seçilen item'ı sıfırla (mask gibi)
            self.state_data[action] = [0, 0, 0, 0]
            terminated = len(self.selected_indices) == self.num_items

        truncated = False
        observation = self.state_data.flatten().astype(np.float32)
        
        return observation, reward, terminated, truncated, {"load": self.current_load}
    # Eğitim Parametreleri
import collections

class ReplayBuffer:
    def __init__(self, capacity=5000):
        self.buffer = collections.deque(maxlen=capacity)
    
    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size):
        # Rastgele örnekleme yaparak korelasyonu kırıyoruz
        batch = random.sample(self.buffer, batch_size)
        state, action, reward, next_state, done = zip(*batch)
        return (np.array(state), action, reward, np.array(next_state), done)
    
    def __len__(self):
        return len(self.buffer)
TRUCK_CAPACITY = 100 # Tırın toplam taşıma kapasitesi
EPISODES = 200        # Ajanın kaç kez simülasyon yapacağı

env = AfetLojistikEnv(truck_capacity=TRUCK_CAPACITY)
input_dim = env.observation_space.shape[0]+1
output_dim = env.action_space.n
import torch
import torch.nn as nn
import torch.optim as optim
import random
class QNetwork(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(QNetwork, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, output_dim)
        )

    def forward(self, x):
        return self.net(x)
# Model ve Optimizer
model = QNetwork(input_dim, output_dim)
optimizer = optim.Adam(model.parameters(), lr=0.0005) # Daha kararlı öğrenme için lr düşürüldü
criterion = nn.MSELoss()

import torch
import random
import numpy as np

def start_training_with_capacity():
    print("Target Model + Replay Buffer + Remaining Capacity ile eğitim başlıyor...")
    
    # --- Hiperparametreler ve Tanımlamalar ---
    gamma = 0.98
    epsilon = 1.0           # Başlangıç: Tamamen keşif
    epsilon_decay = 0.992    # Her bölümde epsilonu %0.8 azalt
    min_epsilon = 0.05       # Minimum keşif sınırı
    batch_size = 64
    update_target_every = 15 
    
    # Target Model Kurulumu
    # Giriş boyutu: state_raw.flatten() + 1 (remaining_ratio)
    target_model = QNetwork(input_dim , output_dim) 
    target_model.load_state_dict(model.state_dict(),strict=True)
    target_model.eval()
    
    buffer = ReplayBuffer(10000)
    
    for ep in range(EPISODES):
        # 1. Reset aşamasında kapasiteyi ve başlangıç state'ini hazırla
        state_raw, _ = env.reset()
        current_load = 0
        rem_ratio = (TRUCK_CAPACITY - current_load) / TRUCK_CAPACITY
        
        # ✅ remaining_ratio state'e ekleniyor
        state = np.append(state_raw.flatten(), [rem_ratio])
        
        total_reward = 0
        done = False
        
        while not done:
            state_t = torch.tensor(state, dtype=torch.float32)
            
            # Aksiyon Seçimi (Epsilon-Greedy)
            if random.random() < epsilon:
                action = env.action_space.sample()
            else:
                with torch.no_grad():
                    action = model(state_t).argmax().item()
            
            # Adım at
            next_state_raw, reward, terminated, truncated, info = env.step(action)
            current_load = info['load']
            
            # ✅ Yeni remaining_ratio'yu hesapla ve next_state'e ekle
            next_rem_ratio = (TRUCK_CAPACITY - current_load) / TRUCK_CAPACITY
            next_state = np.append(next_state_raw.flatten(), [next_rem_ratio])
            
            done = terminated or truncated
            buffer.push(state, action, reward, next_state, done)
            
            if len(buffer) > batch_size:
                b_s, b_a, b_r, b_ns, b_d = buffer.sample(batch_size)
                
                b_s_t = torch.tensor(b_s, dtype=torch.float32)
                b_ns_t = torch.tensor(b_ns, dtype=torch.float32)
                b_r_t = torch.tensor(b_r, dtype=torch.float32)
                b_d_t = torch.tensor(b_d, dtype=torch.float32)
                # ✅ Action tensor dtype düzeltmesi (Long/Int64)
                b_a_t = torch.tensor(b_a, dtype=torch.long)
                
                # Target Model ile Hedef Q Hesapla
                with torch.no_grad():
                    max_next_q = target_model(b_ns_t).max(1)[0]
                    target_q = b_r_t + (gamma * max_next_q * (1 - b_d_t))
                
                # Karar ağını güncelle
                current_q = model(b_s_t).gather(1, b_a_t.unsqueeze(1)).squeeze(1)
                loss = criterion(current_q, target_q)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            
            state = next_state
            total_reward += reward
            # ... (Döngü sonu)
        
        
        # Her 15 bölümde bir ajanın yaptığı son seçimi detaylıca raporla
            if (ep + 1) % update_target_every == 0:
                print(f"\n--- Bölüm {ep+1} Özet Raporu ---")
                print(f"Toplam Yük: {current_load}/{TRUCK_CAPACITY} | Toplam Ödül: {total_reward:.2f}")
                print("Seçilen İhtiyaçlar:")
                
                for idx in env.selected_indices:
                    item = env.processed_data[idx]
                    print(f" > ID: {item['id']} | Aciliyet: {item['priority']:.2f} | Miktar: {item['amount']} | Mesafe Cezası: {item['distance_penalty']}")
                print("-" * 30 + "\n")
            
        # ✅ Epsilon Decay (Keşif oranını zamanla azalt)
        epsilon = max(min_epsilon, epsilon * epsilon_decay)
            
        # Belirli aralıklarla hedef ağı güncelle
        if (ep + 1) % update_target_every == 0:
            target_model.load_state_dict(model.state_dict())
            print(f"Bölüm {ep+1} tamamlandı. Epsilon: {epsilon:.2f} | Ödül: {total_reward:.2f}")

    # ✅ Modeli döndür
    return model

# Çalıştır
final_model = start_training_with_capacity()