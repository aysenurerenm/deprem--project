from django.db import close_old_connections
import numpy as np
import torch
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



GLOBAL_DATA = {}


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


def get_graph_vector_state(depot_id):
    
    # Mevcut DB çekme fonksiyonunu kullanıyoruz
    talepler = Ihtiyac.objects.select_related('urunID', 'alanID').filter(
    ihtiyacdurum='Bekliyor',
    alanID__depoID=depot_id
)
    processed_data = []
    node_list = []
    current_time = django_tz.now()
    MAX_DEMAND = 100.0   # datasetine göre ayarla
    MAX_URGENCY = 5.0   
    for talep in talepler:
        # 1. ACİLİYET
        base_urgency = float(talep.urunID.Aciliyet)
        
        # 2. AGING (YAŞLANMA)
        wait_delta = current_time - talep.talepZamanı
        wait_hours = max(0, wait_delta.total_seconds() / 3600)
        aging_factor = (1.05) ** wait_hours 

        # 3. LOJİSTİK/MESAFE CEZASI
        ana_depo_id = 16
       
        stok_kaydi = DepoUrunler.objects.filter(
    depoID=depot_id,
    urunID=talep.urunID
).first()
        if not stok_kaydi or stok_kaydi.urunMiktar < talep.ihtiyacmiktar:
            alternatif_stok = DepoUrunler.objects.filter(
                urunID=talep.urunID, 
                urunMiktar__gte=talep.ihtiyacmiktar
            ).exclude(depoID=ana_depo_id).exists()
            distance_penalty = 2.5 if alternatif_stok else 5.0
        else:
            distance_penalty = 1.0

        amount = float(talep.ihtiyacmiktar)
        amount_norm = amount / MAX_DEMAND

        # 🔥 URGENCY NORMALIZE
        urgency_norm = base_urgency / MAX_URGENCY

        # 🔥 RELATIVE LOCATION (çok önemli)
        lat = float(talep.alanID.enlem)
        lon = float(talep.alanID.boylam)

        lat_norm = (lat - 38.41) / 0.1
        lon_norm = (lon - 27.12) / 0.1

        # 🔥 distance penalty scale
        distance_penalty_norm = distance_penalty / 5.0

        # ✅ NORMALIZED FEATURE VECTOR
        node_features = [
            urgency_norm,
            aging_factor,
            amount_norm,
            lat_norm,
            lon_norm,
            distance_penalty_norm
        ]

        node_list.append(node_features)

        processed_data.append({
            'id': talep.ihtiyacID,
            'priority': base_urgency * aging_factor,
            'distance_penalty': distance_penalty,
            'amount': amount,
            "enlem": lat,
            "boylam": lon
        })

    # matrix
    state_matrix = np.array(node_list, dtype=np.float32)

    return state_matrix, processed_data

def load_data_once(depot_id):
    global GLOBAL_DATA

    if depot_id not in GLOBAL_DATA:
        print(f"📦 DB'den veri çekiliyor: Depot {depot_id}")
        data = get_graph_vector_state(depot_id)

        if data is not None and len(data) == 2:
            GLOBAL_DATA[depot_id] = data   # ✅ DOĞRU
        else:
            print(f"HATA: Depot {depot_id} için veri yok!")
            return None

    return GLOBAL_DATA[depot_id]
# Pointer Network kullanımı için PyTorch Tensor'e çevirme (Opsiyonel)
# state_tensor = torch.FloatTensor(get_graph_vector_state())
import torch
import torch.nn as nn
import torch.nn.functional as F

class Encoder(nn.Module):
    def __init__(self, input_dim=6, hidden_dim=128, nhead=8, num_layers=3):
        super(Encoder, self).__init__()
        self.hidden_dim = hidden_dim
        
        # 1. Girdi Özelliklerini Gömme (Embedding)
        # 4 özellikten 128 boyutlu zengin bir temsile geçiş
        self.embedding = nn.Linear(input_dim, hidden_dim)
        
        # 2. Transformer Katmanları
        # nhead=8 olduğu için her kafa 16 boyuta (128/8) odaklanır.
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim, 
            nhead=nhead, 
            dim_feedforward=hidden_dim * 4,
            dropout=0.1,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # 3. Norm Katmanı (Eğitimi stabilize eder)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x, mask=None):
        """
        x: (Batch, Node_Sayısı, 4)
        mask: (Batch, Node_Sayısı) -> Hangi düğümlerin aktif olduğunu belirtir
        """
        # Linear embedding
        # (Batch, N, 4) -> (Batch, N, 128)
        x = self.embedding(x)
        
        # Transformer işlemleri
        # mask parametresi, 'padding' olan veya işlem dışı düğümleri attention mekanizmasından dışlar
        # src_key_padding_mask True olan değerleri görmezden gelir.
        if mask is not None:
            # Transformer maskesi True/False (veya 1/0) şeklinde çalışır
            # 0'ları (maskelenmiş) True yaparak dikkatten çıkarıyoruz
            key_padding_mask = (mask == 0)
            encoded_nodes = self.transformer(x, src_key_padding_mask=key_padding_mask)
        else:
            encoded_nodes = self.transformer(x)
            
        encoded_nodes = self.norm(encoded_nodes)
        
        # 4. Global Context (Bağlam Vektörü)
        # Sadece aktif düğümlerin ortalamasını alarak tüm sahanın durumunu özetler
        if mask is not None:
            # Maskelenmiş düğümleri 0'la çarpıp sadece gerçek düğümlerin ortalamasını alıyoruz
            mask_expanded = mask.unsqueeze(-1).expand_as(encoded_nodes)
            context = (encoded_nodes * mask_expanded).sum(dim=1) / mask.sum(dim=1, keepdim=True)
        else:
            context = torch.mean(encoded_nodes, dim=1)
            
        return encoded_nodes, context
import torch
import torch.nn as nn
import torch.nn.functional as F

class PointerAttention(nn.Module):
    def __init__(self, hidden_dim=128):
        super(PointerAttention, self).__init__()
        self.hidden_dim = hidden_dim
        
        # Lineer dönüşümler (Düşünce uzayına izdüşüm)
        self.W_query = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.W_ref = nn.Linear(hidden_dim, hidden_dim, bias=False)
        
        # Skorlama vektörü (V): Tanh çıktısını tek bir skora indirger
        self.v = nn.Parameter(torch.empty(hidden_dim))
        nn.init.uniform_(self.v, -1/math.sqrt(hidden_dim), 1/math.sqrt(hidden_dim))

    def forward(self, decoder_hidden, encoded_nodes, mask=None):
        """
        decoder_hidden: Tırın o anki durumu/özeti (Batch, Hidden_Dim)
        encoded_nodes: Encoder'dan gelen düğüm temsilcileri (Batch, N, Hidden_Dim)
        mask: Seçilebilir düğümler (Batch, N) -> 1: Seçilebilir, 0: Maskeli
        """
        batch_size, num_nodes, _ = encoded_nodes.size()

        # 1. Query ve Reference Hazırlığı
        # Query (Sorgu): "Şu an neye ihtiyacım var?"
        query = self.W_query(decoder_hidden).unsqueeze(1) # (B, 1, H)
        # Ref (Referans): "Elimdeki seçenekler neler?"
        ref = self.W_ref(encoded_nodes) # (B, N, H)

        # 2. Skor Hesaplama (Bahdanau İçeriği)
        # query + ref yayını (broadcasting) ile her düğüm için bir enerji değeri üretilir
        energy = torch.tanh(query + ref) # (B, N, H)
        
        # Enerjiyi skora dönüştür (V vektörü ile ağırlıklı toplam)
        # (B, N, H) * (H) -> (B, N)
        score = torch.sum(self.v * energy, dim=-1)

        # 3. Maskeleme
        # Seçilmemesi gereken (stok bitmiş veya daha önce seçilmiş) düğümleri engelle
        if mask is not None:
            # Maske 0 (veya False) olan yerleri eksi sonsuzla doldur ki softmax'te 0 çıksınlar
            score = score.masked_fill(mask == 0, -1e9)
        score = score - torch.max(score, dim=-1, keepdim=True)[0]
        # 4. Olasılık Dağılımı (Softmax)
        # Hangi düğümün seçilme olasılığı daha yüksek?
        
        probs = F.softmax(score, dim=-1)
        if mask.sum(dim=-1).min() == 0:
            probs = torch.where(torch.isnan(probs), torch.ones_like(probs) * 1e-7, probs)
            probs = probs / probs.sum(dim=-1, keepdim=True)
        
        return probs

import torch
import torch.nn as nn
from torch.distributions import Categorical

class PPOAgent(nn.Module):
    def __init__(self, node_dim=9, hidden_dim=128):
        super(PPOAgent, self).__init__()
        # Ortak Özellik Çıkarıcı (Encoder)
        self.encoder = Encoder(node_dim, hidden_dim)
        
        # ACTOR: Aksiyon olasılıklarını belirleyen parmak (Pointer)
        self.pointer = PointerAttention(hidden_dim)
        
        # CRITIC: Durumun değerini (V-Value) tahmin eden kafa
        # Context vektörünü (sahanın özeti) alıp bir puan verir
        self.critic_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, nodes, mask):
        """
        Modelin hem Actor hem Critic çıktılarını aynı anda üretir (Eğitim için)
        """
        encoded_nodes, context = self.encoder(nodes, mask)
        
        # Actor kısmı: Olasılık dağılımı
        probs = self.pointer(context, encoded_nodes, mask)
        
        # Critic kısmı: Durum değeri (State Value)
        state_value = self.critic_head(context)
        
        return probs, state_value

    def act(self, nodes, mask):
        """
        Sahada gerçek zamanlı karar verme anı
        """
        probs, state_value = self.forward(nodes, mask)
        
        # Olasılıklara göre bir dağılım oluştur (Categorical)
        dist = Categorical(probs)
        
        # Dağılımdan bir aksiyon (ihtiyaç indeksi) seç
        action = dist.sample()
        
        # PPO için gerekli olan log_prob ve entropy değerlerini döndür
        return action, dist.log_prob(action), dist.entropy(), state_value
def update_ppo(agent, optimizer, states, masks, actions, old_log_probs, returns, advantages):
    # 1. Yeni olasılıkları ve değerleri al
    new_probs, state_values = agent(states, masks)
    dist = torch.distributions.Categorical(new_probs)
    new_log_probs = dist.log_prob(actions)
    entropy = dist.entropy().mean()

    # 2. Ratio (Oran) Hesaplama: Yeni Politika / Eski Politika
    # log uzayında çıkarma, normal uzayda bölmeye eşittir.
    ratio = torch.exp(new_log_probs - old_log_probs)

    # 3. PPO Clip Loss (Actor Kaybı)
    # Modelin bir adımda %20'den fazla değişmesini engeller (clip_epsilon=0.2)
    surr1 = ratio * advantages
    surr2 = torch.clamp(ratio, 0.8, 1.2) * advantages
    policy_loss = -torch.min(surr1, surr2).mean()

    # 4. Value Loss (Critic Kaybı)
    # Critic'in ödül tahmini gerçek ödüllere (returns) ne kadar yakın?
    value_loss = F.mse_loss(state_values.squeeze(), returns)

    # 5. Toplam Kayıp (Loss)
    # Entropy bonus: Modelin tamamen aynı şeye takılıp kalmasını (overfitting) engeller
    loss = policy_loss + 0.5 * value_loss - 0.01 * entropy

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
def haversine_distance(lat1, lon1, lat2, lon2):
    # Dünya yarıçapı (km)
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

class AfetLojistikEnv:
    def __init__(self,depot_id, truck_max_capacity=100):
        self.depot_id = depot_id
        self.max_capacity = truck_max_capacity
        self.current_capacity = truck_max_capacity
        self.depot_lat, self.depot_lon = 38.41, 27.12 
        self.last_lat, self.last_lon = self.depot_lat, self.depot_lon
        self.mask = None # Seçilenlerin kaydı
        self.state_data = None
        self.processed_data = None

    def reset(self):
        # GLOBAL_DATA'dan oku
        if self.depot_id not in GLOBAL_DATA:
            raise ValueError(f"Depo {self.depot_id} verisi önceden yüklenmemiş!")

        # Orijinal veriyi bozmamak için .copy() kullanmak çok KRİTİK
        state_matrix_orig, processed_info_orig = GLOBAL_DATA[self.depot_id]
        
        # Derin kopyalama (RAM üzerindeki orijinal listeyi korur)
        self.state_data = np.copy(state_matrix_orig)
        self.processed_data = [item.copy() for item in processed_info_orig]
        
        num_nodes = self.state_data.shape[0]
        self.last_lat, self.last_lon = self.depot_lat, self.depot_lon
        self.current_capacity = self.max_capacity
        self.mask = torch.ones(num_nodes, dtype=torch.float32)

        # Kapasite ve Konum özelliklerini ekle
        extra_features = np.array([
            [self.current_capacity, self.last_lat, self.last_lon]
            for _ in range(num_nodes)
        ], dtype=np.float32)

        self.state_data = np.concatenate([self.state_data, extra_features], axis=1)
        return torch.FloatTensor(self.state_data), self.get_combined_mask()

        
    def get_combined_mask(self):
        """Hem daha önce seçilenleri hem de kapasiteyi aşanları maskeler."""
        combined_mask = self.mask.clone()
        for i, talep in enumerate(self.processed_data):
            # Eğer ürün zaten seçildiyse veya ağırlığı kalan kapasiteden fazlaysa kapat
            if self.mask[i] == 0 or talep['amount'] > self.current_capacity:
                combined_mask[i] = 0
        return combined_mask
    

    def step(self, action_idx):
        # 1. Seçilen ana talep bilgilerini al
        main_talep = self.processed_data[action_idx]
        target_lat = float(main_talep['enlem'])
        target_lon = float(main_talep['boylam'])
        
        # Mesafe hesapla (Mevcut konumdan yeni konuma)
        distance = haversine_distance(self.last_lat, self.last_lon, target_lat, target_lon)
        
        # Toplam ödül ve işlem gören talepler için sayaç
        step_reward = 0
        processed_count = 0
        
        # 2. AYNI ALANDAKİ TÜM TALEPLERİ BUL VE TOPLA
        # processed_data içinde dönerek aynı koordinatlı ve henüz seçilmemişleri buluyoruz
        for i, talep in enumerate(self.processed_data):
            if self.mask[i] == 1:  # Eğer hala bekliyorsa
                # Koordinat kontrolü (Çok küçük bir tolerans ile: 0.0001 yaklaşık 10 metre)
                is_same_location = (abs(float(talep['enlem']) - target_lat) < 0.0001 and 
                                   abs(float(talep['boylam']) - target_lon) < 0.0001)
                
                if is_same_location:
                    # Kapasite kontrolü
                    if talep['amount'] <= self.current_capacity:
                        # İşlemi gerçekleştir
                        self.current_capacity -= talep['amount']
                        self.mask[i] = 0  # Maskele (bir daha seçilmesin)
                        
                        # Bu talep için ödül hesapla
                        # (Öncelik ve mesafe cezasını kullanarak)
                        talep_reward = (talep['priority']**3 * 100) / talep['distance_penalty']
                        step_reward += talep_reward
                        processed_count += 1
                    else:
                        # Kapasite yetmiyorsa bu alandaki diğer küçük taleplere bakmaya devam edebilir 
                        # veya burada kesebiliriz. Devam etmesi daha verimlidir.
                        continue

        # 3. MESAFE CEZASI / ÖDÜLÜ (Sadece bir kez uygulanır)
        distance_penalty = -2 * (distance ** 1.5)
        
        # Eğer birden fazla ihtiyacı tek seferde karşıladıysa bonus ver
        if processed_count > 1:
            distance_penalty += (processed_count * 10) # "Verimli toplama" bonusu
            print(f"⚡ AYNI ALANDA {processed_count} İHTİYAÇ BİRDEN KARŞILANDI!")

        final_reward = step_reward + distance_penalty
        
        # 4. Konumu Güncelle
        self.last_lat, self.last_lon = target_lat, target_lon
        
        # Yeni maskeyi al (Kalan kapasiteye göre güncel)
        new_mask = self.get_combined_mask()
        
        # Bitiş durumu
        done = (new_mask.sum() == 0)
        
        # Sefer sonu doluluk bonusu/cezası
        if done:
            safe_capacity = max(0, self.current_capacity)
            if safe_capacity == 0:
                final_reward += 15 # Tam doluluk bonusu
            else:
                final_reward -= (safe_capacity / self.max_capacity) * 5

        # State güncelleme (Kapasite ve konum bilgisini vektöre işle)
        num_nodes = self.state_data.shape[0]
        extra_features = np.array([
            [self.current_capacity, self.last_lat, self.last_lon]
            for _ in range(num_nodes)
        ], dtype=np.float32)
        
        self.state_data = np.concatenate([self.state_data[:, :6], extra_features], axis=1)

        return torch.FloatTensor(self.state_data), new_mask, final_reward, done
import torch
import numpy as np
import random
# Dosyanın üst kısmındaki GLOBAL_DATA kısmını şu şekilde yönetelim
GLOBAL_DATA = {}

def preload_all_depots(depots):
    """Eğitim başlamadan önce DB ile işi bitirir."""
    global GLOBAL_DATA
    for d_id in depots:
        print(f"📦 Veritabanından veri ön-yüklemesi yapılıyor: Depo {d_id}")
        data = get_graph_vector_state(d_id)
        if data is not None and len(data[1]) > 0:
            # Önemli: state_matrix ve processed_info'yu kaydediyoruz
            GLOBAL_DATA[d_id] = data 
        else:
            print(f"⚠️ Uyarı: Depo {d_id} için veri bulunamadı!")
    
    # DB bağlantılarını kapat (Artık ihtiyacımız yok)
    from django.db import connections
    for conn in connections.all():
        conn.close()
    print("🔌 DB bağlantıları güvenli bir şekilde kapatıldı.")
def train():
    # 1. Başlangıç Ayarları
    depots = [16, 17, 18, 19]
    
    # Verileri RAM'e çek ve DB'yi serbest bırak
    preload_all_depots(depots)
    
    # Sadece verisi olan depoları listeye al
    active_depots = list(GLOBAL_DATA.keys())
    if not active_depots:
        print("❌ Eğitilecek veri bulunamadı. Program sonlandırılıyor.")
        return

    # Ajan ve Optimizer (node_dim: 9, hidden_dim: 128)
    agent = PPOAgent(node_dim=9, hidden_dim=128)
    optimizer = torch.optim.Adam(agent.parameters(), lr=3e-4)
    
    epochs = 100 
    
    print(f"🚀 Eğitim Başlıyor | Aktif Depolar: {active_depots} | Epoch: {epochs}")

    for epoch in range(epochs):
        # Her epoch başında rastgele bir depo seç (Çeşitlilik için)
        selected_depot = random.choice(active_depots)
        env = AfetLojistikEnv(depot_id=selected_depot)
        
        # Deneyim Havuzu
        states, masks, actions, log_probs, rewards, values, dones = [], [], [], [], [], [], []
        
        # Ortamı sıfırla (Artık sadece RAM'den kopyalama yapar)
        state, mask = env.reset()
        talep_sayisi = len(env.processed_data)
        
        # Dinamik Horizon: Mevcut talep sayısına göre adım belirle
        T_horizon = max(256, talep_sayisi * 2) 
        epoch_total_reward = 0
        
        for t in range(T_horizon):
            # Maske Kontrolü: Gidecek yer kalmadıysa resetle
            if mask.sum() == 0:
                state, mask = env.reset()
                if mask.sum() == 0: break 

            # 1. Modelden aksiyon al
            # state: (node_sayisi, 9), mask: (node_sayisi)
            action, log_prob, entropy, val = agent.act(state.unsqueeze(0), mask.unsqueeze(0))
            
            # 2. Ortamda adım at
            next_state, next_mask, reward, done = env.step(action.item())
            
            # 3. Verileri kaydet
            states.append(state)
            masks.append(mask)
            actions.append(action)
            log_probs.append(log_prob)
            rewards.append(reward)
            values.append(val)
            dones.append(done)
            
            epoch_total_reward += reward
            state = next_state
            mask = next_mask
            
            # Eğer bir sefer (rota) tamamlandıysa tırı resetle ama epoch'a devam et
            if done:
                state, mask = env.reset()

        # --- GÜNCELLEME ZAMANI (PPO) ---
        if len(states) < 2:
            continue

        # Listeleri Tensor'e çevir
        s_vec = torch.stack(states)
        m_vec = torch.stack(masks)
        a_vec = torch.stack(actions)
        lp_vec = torch.stack(log_probs).detach()
        v_vec = torch.stack(values).detach()
        
        # Avantaj ve Return Hesaplama
        returns = []
        discounted_sum = 0
        for r, d in zip(reversed(rewards), reversed(dones)):
            if d: discounted_sum = 0
            discounted_sum = r + 0.99 * discounted_sum
            returns.insert(0, discounted_sum)
        
        returns = torch.tensor(returns, dtype=torch.float32)
        advantages = returns - v_vec.squeeze()
        
        # Normalize avantaj
        if len(advantages) > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # Model Parametrelerini Güncelle
        update_ppo(agent, optimizer, s_vec, m_vec, a_vec, lp_vec, returns, advantages)
        
        # İstatistikleri Yazdır
        avg_reward = epoch_total_reward / len(states)
        print(f"📊 Epoch {epoch+1}/{epochs} | Depo: {selected_depot} | Ort. Ödül: {avg_reward:.2f} | Adım: {len(states)}")
        
        # Periyodik Kayıt
        if (epoch + 1) % 10 == 0:
           # torch.save(agent.state_dict(), f"afet_model_epoch_{epoch+1}.pth")
            print(f"💾 Ara model kaydedildi: epoch_{epoch+1}")

    # Final Kayıt
    torch.save(agent.state_dict(), "afet_lojistik_final_model.pth")
    print("✅ Eğitim tamamlandı ve final modeli 'afet_lojistik_final_model.pth' adıyla kaydedildi!")

if __name__ == "__main__":
    train()