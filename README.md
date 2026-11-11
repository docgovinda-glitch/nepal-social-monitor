# 🇳🇵 Nepal Media & Geo-Political Trends Monitor

A real-time monitoring and classification tool designed to track:
1. **Top 34 Leading Nepali and English Online News Portals** (with 8-category structured classification).
2. **Nepal in Indian Media** (Dedicated monitoring of how top Indian newspapers and digital portals report on Nepal).
3. **Date & Timestamp Filter** (Select any exact date and time in Nepal Standard Time to view articles published from that point up to now).
4. **Live Social Media Monitor** for **X (formerly Twitter)** in **Nepal**.

---

## 🚀 Live Dashboard
Open your web browser and go to:
👉 **[http://localhost:8501](http://localhost:8501)**

---

## 📅 Date & Timestamp Filter
Located directly in the left sidebar under **"📅 Date & Timestamp Filter"**:
- **Quick Horizon Presets**:
  - `Past 1 Hour`
  - `Past 3 Hours`
  - `Past 6 Hours`
  - `Past 12 Hours`
  - `Past 24 Hours`
  - `Today (Since 00:00 NPT)`
  - `All Recent Articles (Default)`
- **Custom Date & Timestamp Picker**:
  - Pick an exact **Starting Date** (e.g. `Nov 06, 2026`).
  - Pick an exact **Starting Time** in Nepal Time (e.g. `10:30 AM NPT`).
  - The dashboard instantly filters all 34 Nepali portals, Indian media coverage, and exportable datasets to show **only articles published from that selected time up to the current moment**.

---

## 🇮🇳 Dedicated Menu: "Nepal in Indian Media"
Tracks what leading Indian national dailies, broadcast networks, and border region newspapers are publishing about Nepal:
- **The Indian Express** (Dedicated Nepal desk & World section)
- **The Hindu** (Diplomatic & foreign affairs reporting)
- **India Today** (Dedicated Nepal section & international reporting)
- **The Print** (Strategic affairs & South Asian diplomacy)
- **Hindustan Times** (World & South Asia desk)
- **Business Standard** (Bilateral trade, hydropower & economy)
- **NDTV** (National broadcast network)
- **Amar Ujala** (Top Hindi border newspaper covering Nepal)

---

## 📑 Structured Nepali Media Classification (8 Categories)
Every article published across Nepal's online news portals is automatically classified into the following 8 structured categories:
1. **🇮🇳 India in Nepal**: Indian activities, Embassy, visits, bilateral deals, SAARC, BIMSTEC, borders.
2. **🇨🇳 China in Nepal**: Chinese projects, BRI, Embassy, visits, border points, investments.
3. **🇵🇰 Pakistan in Nepal**: Diplomatic, trade, and bilateral affairs.
4. **🇧🇩 Bangladesh in Nepal**: Bilateral trade, energy/power exports, transit, diplomatic news.
5. **🏛 Nepal – Internal Politics**: Domestic political developments, parties, elections, parliament, constitution, judiciary.
6. **🌐 Nepal – External Relations (Others)**: UN, EU, World Bank, IMF, US, Japan, Gulf states, embassies.
7. **💰 Economy**: Markets, banking, monetary policy, trade, business, macroeconomic indicators, inflation.
8. **📌 Others**: Trending public interest news excluding politics (tech, climate, sports, culture, disaster).

---

## 📰 Top 34 Monitored Nepali Media Portals
- **Nepali (22):** eKantipur, Setopati, Annapurna Post, Naya Patrika, NepalKhabar, Gorkhapatra, News of Nepal, Nepal Aaja, Nepal News, OnlineKhabar, Ratopati, Nagarik News, Nepal Press, Baahrakhari, Himal Press, Deshsanchar, Shilapatra, Nepal Live, Image Khabar, Khabarhub, TechPana, ArthaSarokar.
- **English (12):** The Kathmandu Post, The Himalayan Times, MyRepublica, The Annapurna Express, Setopati (EN), Rising Nepal, NepalKhabar (EN), Nepal News (EN), OnlineKhabar (EN), Ratopati (EN), Khabarhub (EN), Nepali Times.

---

## 📈 Analytics & CSV / Word Export (with Article Selector & Full News Text)
Under the **"📈 Analytics & CSV Export"** tab:
- **Interactive Article Selector**: Each news item features a selectable checkbox column (`Export to Word?`) allowing you to pick exactly which articles are included in the Word Document export.
- **Quick Selection Controls**: One-click **☑️ Select All** and **⬜ Deselect All** buttons with live count indicators.
- **Word Document (.docx Export)**: Exports selected news grouped under the 7 strictly ordered categories with **yellow highlighted headers in ALL CAPS**, bulleted & italicized headlines, source names, full article text, and URLs.
- **Headline (Original)**: Retains the original headline in its published language, with the English translation placed starting on the next line within the same cell for Devanagari (Nepali/Hindi) headlines.
- **Full Content**: Extracts the actual full body text of the news article directly from the source portal.
- **Structured Category & Source / Portal**: Auto-categorized under the 8 geo-political buckets and tagged by portal.
- **Exact Timestamp**: Shows the exact publication date and time in Nepal Standard Time (NPT).
- **Article Link**: Clickable link to the source article.
- **Excel & CSV Ready**: Uses UTF-8 with BOM (`utf-8-sig`) so that Devanagari script (Nepali/Hindi) renders cleanly in Microsoft Excel, Google Sheets, and data science notebooks without font corruption.

---

## 🔁 To Launch Anytime:
```bash
cd /Users/pobpkf/.gemini/antigravity/scratch/nepal-social-monitor
./run.sh
```
