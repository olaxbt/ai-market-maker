// Curated universe of HK + US stocks for Futu OpenD backtest ticker selector.
// Priority: high-liquidity, frequently traded, major indices constituents.

export interface FutuStockEntry {
  code: string;       // HK.00700 or US.AAPL
  name: string;       // Tencent Holdings
  suffix: string;     // Tencent / AAPL
}

const HK_STOCKS: FutuStockEntry[] = [
  // ── Top 30 by market cap / liquidity ──
  { code: "HK.00700", name: "Tencent Holdings", suffix: "Tencent" },
  { code: "HK.09988", name: "Alibaba Group", suffix: "Alibaba" },
  { code: "HK.03690", name: "Meituan", suffix: "Meituan" },
  { code: "HK.09999", name: "NetEase", suffix: "NetEase" },
  { code: "HK.01810", name: "Xiaomi Corp", suffix: "Xiaomi" },
  { code: "HK.09618", name: "JD.com", suffix: "JD.com" },
  { code: "HK.01211", name: "BYD Co", suffix: "BYD" },
  { code: "HK.00388", name: "HKEX", suffix: "HKEX" },
  { code: "HK.02318", name: "Ping An Insurance", suffix: "Ping An" },
  { code: "HK.00883", name: "CNOOC", suffix: "CNOOC" },
  { code: "HK.00941", name: "China Mobile", suffix: "China Mobile" },
  { code: "HK.01299", name: "AIA Group", suffix: "AIA" },
  { code: "HK.00005", name: "HSBC Holdings", suffix: "HSBC" },
  { code: "HK.00011", name: "Hang Seng Bank", suffix: "HSB" },
  { code: "HK.00016", name: "SHK Properties", suffix: "SHK Prop" },
  { code: "HK.00027", name: "Galaxy Entertainment", suffix: "Galaxy" },
  { code: "HK.00066", name: "MTR Corp", suffix: "MTR" },
  { code: "HK.00001", name: "CK Hutchison", suffix: "CK Hutch" },
  { code: "HK.00002", name: "CLP Holdings", suffix: "CLP" },
  { code: "HK.00003", name: "HK & China Gas", suffix: "Towngas" },
  { code: "HK.00006", name: "Power Assets", suffix: "Power Assets" },
  { code: "HK.00012", name: "Henderson Land", suffix: "Henderson" },
  { code: "HK.00017", name: "New World Dev", suffix: "New World" },
  { code: "HK.00019", name: "Swire Pacific", suffix: "Swire" },
  { code: "HK.00083", name: "Sino Land", suffix: "Sino Land" },
  { code: "HK.00101", name: "Hang Lung Prop", suffix: "Hang Lung" },
  { code: "HK.00267", name: "CITIC", suffix: "CITIC" },
  { code: "HK.00288", name: "Wharf REIC", suffix: "Wharf REIC" },
  { code: "HK.00291", name: "China Resources Beer", suffix: "CR Beer" },
  { code: "HK.00316", name: "OOIL (Orient Overseas)", suffix: "OOIL" },

  // ── Tech / Internet / Innovation ──
  { code: "HK.00780", name: "Tongcheng Travel", suffix: "Tongcheng" },
  { code: "HK.00772", name: "China Literature", suffix: "China Lit" },
  { code: "HK.01024", name: "Kuaishou Technology", suffix: "Kuaishou" },
  { code: "HK.02015", name: "Li Auto", suffix: "Li Auto" },
  { code: "HK.09888", name: "Baidu (HK)", suffix: "Baidu HK" },
  { code: "HK.09899", name: "Cloud Music", suffix: "Cloud Music" },
  { code: "HK.06618", name: "JD Health", suffix: "JD Health" },
  { code: "HK.06690", name: "Haier Smart Home", suffix: "Haier" },
  { code: "HK.06060", name: "ZhongAn Online", suffix: "ZhongAn" },
  { code: "HK.06098", name: "CG Services", suffix: "CG Services" },
  { code: "HK.06186", name: "China Feihe", suffix: "Feihe" },
  { code: "HK.06628", name: "Create Century", suffix: "Create Cent" },
  { code: "HK.09626", name: "Bilibili (HK)", suffix: "Bili HK" },
  { code: "HK.09698", name: "GDS Holdings (HK)", suffix: "GDS HK" },
  { code: "HK.09878", name: "Didi Global (HK)", suffix: "Didi HK" },
  { code: "HK.09901", name: "New Oriental (HK)", suffix: "New Oriental" },
  { code: "HK.09961", name: "Trip.com (HK)", suffix: "Trip.com HK" },
  { code: "HK.09991", name: "Baozun (HK)", suffix: "Baozun HK" },
  { code: "HK.02057", name: "QuantumPharm", suffix: "QuantumPharm" },
  { code: "HK.02162", name: "Keymed Biosciences", suffix: "Keymed" },

  // ── Finance / Insurance / Banks ──
  { code: "HK.01398", name: "ICBC", suffix: "ICBC" },
  { code: "HK.03988", name: "Bank of China", suffix: "BoC" },
  { code: "HK.00939", name: "CCB", suffix: "CCB" },
  { code: "HK.01288", name: "ABC (Ag Bank China)", suffix: "AgBank" },
  { code: "HK.03968", name: "CM Bank", suffix: "CMB" },
  { code: "HK.00998", name: "China CITIC Bank", suffix: "CITIC Bank" },
  { code: "HK.02388", name: "BoC Hong Kong", suffix: "BoC HK" },
  { code: "HK.02628", name: "China Life", suffix: "China Life" },
  { code: "HK.02601", name: "CPIC", suffix: "CPIC" },
  { code: "HK.01339", name: "PICC", suffix: "PICC" },
  { code: "HK.06030", name: "CITIC Securities", suffix: "CITIC Sec" },
  { code: "HK.06881", name: "China Galaxy Sec", suffix: "CGS" },
  { code: "HK.06886", name: "Huatai Sec", suffix: "Huatai Sec" },
  { code: "HK.00322", name: "Tingyi (Master Kong)", suffix: "Master Kong" },

  // ── Consumer / Retail / F&B ──
  { code: "HK.06862", name: "Haidilao", suffix: "Haidilao" },
  { code: "HK.09922", name: "Jiuxian.com", suffix: "Jiuxian" },
  { code: "HK.09863", name: "Luckin Coffee (HK)", suffix: "Luckin HK" },
  { code: "HK.02020", name: "Anta Sports", suffix: "Anta" },
  { code: "HK.02331", name: "Li Ning", suffix: "Li Ning" },
  { code: "HK.06160", name: "BEIGENE", suffix: "BeiGene" },
  { code: "HK.01876", name: "Bud APAC", suffix: "Bud APAC" },
  { code: "HK.09633", name: "Nongfu Spring", suffix: "Nongfu" },
  { code: "HK.02319", name: "Mengniu Dairy", suffix: "Mengniu" },
  { code: "HK.00322", name: "Tingyi (Master Kong)", suffix: "Master Kong" },
  { code: "HK.00151", name: "Want Want China", suffix: "Want Want" },
  { code: "HK.02013", name: "Weimob", suffix: "Weimob" },

  // ── Healthcare / Biotech ──
  { code: "HK.02269", name: "Wuxi Biologics", suffix: "WuXi Bio" },
  { code: "HK.02359", name: "Wuxi AppTec", suffix: "WuXi App" },
  { code: "HK.01093", name: "Shandong Pharma", suffix: "Shandong Pharma" },
  { code: "HK.03320", name: "China Resources Pharma", suffix: "CR Pharma" },
  { code: "HK.03692", name: "Hansoh Pharma", suffix: "Hansoh" },
  { code: "HK.06185", name: "CanSinoBio", suffix: "CanSino" },
  { code: "HK.06669", name: "Akeso", suffix: "Akeso" },
  { code: "HK.09995", name: "Remegen", suffix: "Remegen" },
  { code: "HK.02196", name: "Shanghai Fosun Pharma", suffix: "Fosun Pharma" },

  // ── Property / Infrastructure ──
  { code: "HK.01109", name: "China Resources Land", suffix: "CR Land" },
  { code: "HK.00688", name: "China Overseas Land", suffix: "COLI" },
  { code: "HK.00960", name: "Longfor Group", suffix: "Longfor" },
  { code: "HK.00004", name: "Wharf Holdings", suffix: "Wharf" },
  { code: "HK.01997", name: "Wharf Real Estate", suffix: "Wharf RE" },
  { code: "HK.02007", name: "Country Garden", suffix: "Country Garden" },
  { code: "HK.03333", name: "China Evergrande", suffix: "Evergrande" },
  { code: "HK.00823", name: "Link REIT", suffix: "Link REIT" },
  { code: "HK.01209", name: "China Resources Cement", suffix: "CR Cement" },
  { code: "HK.03311", name: "China State Construction", suffix: "CSC" },

  // ── Energy / Utilities / Telco ──
  { code: "HK.00857", name: "PetroChina", suffix: "PetroChina" },
  { code: "HK.00386", name: "Sinopec", suffix: "Sinopec" },
  { code: "HK.00934", name: "Sinopec Kantons", suffix: "Sinopec Kan" },
  { code: "HK.01088", name: "China Shenhua Energy", suffix: "Shenhua" },
  { code: "HK.02380", name: "China Power", suffix: "China Power" },
  { code: "HK.00916", name: "China Longyuan Power", suffix: "Longyuan" },
  { code: "HK.00762", name: "China Unicom", suffix: "Unicom" },
  { code: "HK.00728", name: "China Telecom", suffix: "China Tel" },
  { code: "HK.01347", name: "Hua Hong Semi", suffix: "Hua Hong" },
  { code: "HK.00981", name: "SMIC", suffix: "SMIC" },
  { code: "HK.02469", name: "Synaptogenix", suffix: "Synapto" },
];

const US_STOCKS: FutuStockEntry[] = [
  { code: "US.AAPL", name: "Apple Inc", suffix: "AAPL" },
  { code: "US.MSFT", name: "Microsoft Corp", suffix: "MSFT" },
  { code: "US.GOOGL", name: "Alphabet (Google)", suffix: "GOOGL" },
  { code: "US.AMZN", name: "Amazon.com", suffix: "AMZN" },
  { code: "US.META", name: "Meta Platforms", suffix: "META" },
  { code: "US.TSLA", name: "Tesla Inc", suffix: "TSLA" },
  { code: "US.NVDA", name: "NVIDIA Corp", suffix: "NVDA" },
  { code: "US.AVGO", name: "Broadcom Inc", suffix: "AVGO" },
  { code: "US.JPM", name: "JPMorgan Chase", suffix: "JPM" },
  { code: "US.V", name: "Visa Inc", suffix: "V" },
  { code: "US.MA", name: "Mastercard Inc", suffix: "MA" },
  { code: "US.UNH", name: "UnitedHealth Group", suffix: "UNH" },
  { code: "US.HD", name: "Home Depot", suffix: "HD" },
  { code: "US.DIS", name: "Walt Disney", suffix: "DIS" },
  { code: "US.ADBE", name: "Adobe Inc", suffix: "ADBE" },
  { code: "US.INTC", name: "Intel Corp", suffix: "INTC" },
  { code: "US.AMD", name: "AMD", suffix: "AMD" },
  { code: "US.SPY", name: "SPDR S&P 500 ETF", suffix: "SPY" },
  { code: "US.QQQ", name: "Invesco QQQ ETF", suffix: "QQQ" },
  { code: "US.IWM", name: "Russell 2000 ETF", suffix: "IWM" },
  { code: "US.GLD", name: "SPDR Gold Shares", suffix: "GLD" },
  { code: "US.SLAM", name: "SLAM Corp", suffix: "SLAM" },
  { code: "US.BRK.B", name: "Berkshire Hathaway B", suffix: "BRK.B" },
  { code: "US.NFLX", name: "Netflix Inc", suffix: "NFLX" },
  { code: "US.SBUX", name: "Starbucks Corp", suffix: "SBUX" },
  { code: "US.UBER", name: "Uber Technologies", suffix: "UBER" },
  { code: "US.PLTR", name: "Palantir Technologies", suffix: "PLTR" },
  { code: "US.TSM", name: "TSMC ADR", suffix: "TSM" },
  { code: "US.BABA", name: "Alibaba ADR", suffix: "BABA" },
  { code: "US.NIO", name: "NIO Inc ADR", suffix: "NIO" },
  { code: "US.XPEV", name: "XPeng ADR", suffix: "XPEV" },
  { code: "US.LI", name: "Li Auto ADR", suffix: "LI" },
];

export function getAllStocks(): FutuStockEntry[] {
  return [...HK_STOCKS, ...US_STOCKS];
}

export const HK_STOCKS_LIST = HK_STOCKS;
export const US_STOCKS_LIST = US_STOCKS;
