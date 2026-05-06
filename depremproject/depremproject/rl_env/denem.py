import torch
import numpy as np
import folium
import os
from datetime import datetime

# Kendi dosyalarından importlar
from ppovepointe import PPOAgent, AfetLojistikEnv, preload_all_depots, GLOBAL_DATA

def test_model(
    model_path="afet_lojistik_final_model.pth", 
    depot_id=19
):
    # 1. VERİ ÖN-YÜKLEME (SQL ve RAM Yönetimi)
    if not GLOBAL_DATA:
        preload_all_depots([depot_id])

    # 2. ENV + MODEL HAZIRLIĞI
    env = AfetLojistikEnv(depot_id=depot_id, truck_max_capacity=100)
    
    try:
        state, mask = env.reset()
    except ValueError as e:
        print(f"❌ Hata: {e}")
        return

    agent = PPOAgent(node_dim=9, hidden_dim=128)
    
    if os.path.exists(model_path):
        agent.load_state_dict(torch.load(model_path, map_location="cpu"))
        print(f"✅ Model yüklendi: {model_path}")
    else:
        print(f"❌ Model dosyası bulunamadı: {model_path}")
        return
        
    agent.eval()

    print(f"🚀 TEST BAŞLADI | Depo: {depot_id} | Kapasite: {env.max_capacity}")

    route = [(env.depot_lat, env.depot_lon)]
    delivered_items = [] # Tüm başarılı teslimatlar
    visited_locations = [] # Harita için benzersiz duraklar
    total_reward = 0
    done = False

    # 3. ROLLOUT (KARAR VERME DÖNGÜSÜ)
    with torch.no_grad():
        while not done:
            # Modelden olasılıkları al
            probs, _ = agent(state.unsqueeze(0), mask.unsqueeze(0))
            probs = probs.squeeze(0)

            # En yüksek olasılıklı geçerli aksiyonu bul
            valid_probs = probs * mask
            if valid_probs.sum() <= 0:
                print("🛑 Gidilebilecek geçerli nokta kalmadı veya kapasite doldu.")
                break
                
            action = torch.argmax(valid_probs).item()
            
            # Seçilen durak bilgilerini (henüz step yapmadan) alalım
            target_node = env.processed_data[action]
            target_lat = target_node['enlem']
            target_lon = target_node['boylam']

            # --- ÖNEMLİ: Mevcut maske durumunu kaydediyoruz ki hangi kalemlerin ---
            # --- bu adımda (step içinde) kapandığını anlayabilelim. ---
            old_mask = env.mask.clone()

            # Adımı gerçekleştir (Artık aynı konumdaki her şeyi topluca bırakıyor)
            state, mask, reward, done = env.step(action)
            total_reward += reward

            # Bu adımda teslim edilen tüm kalemleri tespit et
            # (old_mask'ta 1 olup yeni mask'ta 0 olanlar)
            newly_delivered_count = 0
            for i in range(len(env.mask)):
                if old_mask[i] == 1 and env.mask[i] == 0:
                    item = env.processed_data[i]
                    delivered_items.append(item)
                    newly_delivered_count += 1

            # Harita rotası için konumu ekle
            visited_locations.append({
                "enlem": target_lat,
                "boylam": target_lon,
                "count": newly_delivered_count
            })
            route.append((target_lat, target_lon))

            print(
                f"📍 Durak {len(visited_locations)} | "
                f"Konum: ({target_lat:.4f}, {target_lon:.4f}) | "
                f"Bırakılan Kalem: {newly_delivered_count} | "
                f"Ödül: {reward:.2f} | "
                f"Kalan Cap: {env.current_capacity:.1f}"
            )

    # 4. ANALİZ VE ÖZET
    print("\n" + "="*30)
    print("🏁 SEFER ÖZETİ (TOPLU TESLİMAT)")
    print("="*30)
    if delivered_items:
        avg_p = np.mean([v["priority"] for v in delivered_items])
        total_a = np.sum([v["amount"] for v in delivered_items])
        print(f"✅ Toplam Durak Sayısı   : {len(visited_locations)}")
        print(f"✅ Toplam Teslimat (Adet): {len(delivered_items)}")
        print(f"✅ Toplam Taşınan Miktar : {total_a:.1f} birim")
        print(f"✅ Ortalama Öncelik      : {avg_p:.2f}")
        print(f"✅ Toplam Reward         : {total_reward:.2f}")
        print(f"✅ Doluluk Oranı         : %{((total_a/env.max_capacity)*100):.1f}")
    else:
        print("⚠️ Hiçbir teslimat yapılamadı.")

    # 5. HARİTA OLUŞTURMA
    m = folium.Map(
        location=[env.depot_lat, env.depot_lon],
        zoom_start=13,
        tiles="cartodbpositron"
    )

    folium.Marker(
        [env.depot_lat, env.depot_lon],
        popup="ANA DEPO",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m)

    folium.PolyLine(route, color="blue", weight=4, opacity=0.7).add_to(m)

    for i, loc in enumerate(visited_locations):
        popup_text = (f"Durak: {i+1}<br>"
                      f"Konum: {loc['enlem']:.5f}, {loc['boylam']:.5f}<br>"
                      f"Teslim Edilen Kalem: <b>{loc['count']} adet</b>")
        
        folium.CircleMarker(
            location=[loc["enlem"], loc["boylam"]],
            radius=10,
            popup=popup_text,
            color="darkblue",
            fill=True,
            fill_color="cyan"
        ).add_to(m)

        folium.Marker(
            location=[loc["enlem"], loc["boylam"]],
            icon=folium.DivIcon(html=f'<div style="font-size: 12pt; color: white; background: black; border-radius: 50%; width: 20px; height: 20px; text-align: center; line-height: 20px; font-weight: bold;">{i+1}</div>')
        ).add_to(m)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"toplu_rota_depo_{depot_id}_{timestamp}.html"
    m.save(file_name)
    print(f"📁 Toplu teslimat haritası oluşturuldu: {file_name}")

if __name__ == "__main__":
    test_model()