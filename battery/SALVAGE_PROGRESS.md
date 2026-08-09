# Battery System 旧開発サルベージ・進捗資料

## 目的

過去に開発した Battery 評価システムの成果を、現在の2ch Battery DeviceおよびMini 4WDシミュレーター統合設計へ引き継ぐ。

旧 `battery/` は複数世代の試作コード、仕様、DB、ログを含む。旧コードをそのまま現行実装へ戻すのではなく、評価思想・データ項目・状態判定・ペアリング思想などを設計資産として回収する。

## 現行ハードウェアの扱い

- 新しい2ch Battery Deviceを現行ハードウェアの正とする。
- 旧デバイスは配線ミスが判明しているため、旧ログの測定値を性能評価の根拠にしない。
- 旧ログは開発履歴、データ項目、通信形式、UI/評価設計の参考資料として扱う。
- 現行2chコードのベースは `battery/arduino/battery_discharge_2ch_v1.ino`。実機ではチャンネル等の調整が入っているため、これを最終配線確定版とは扱わない。

## 過去開発時点の進捗認識

### Phase 1：計測・制御 — 100%

当時「完成」と認識。

- 5A電流制御
- 電圧測定
- シリアル通信
- START / STOP
- stop_reason
- 実機測定

### Phase 2：評価ロジック — 90〜95%

単体評価は実用レベルと認識。

- 平均電圧
- 平均電流
- 電圧ドロップ
- 安定性
- 簡易容量
- 総合スコア

未完了・要再設計：

- dtを用いた厳密容量計算
- stop_reasonとの連動

### Phase 3：育成モード — 0%

PWMプリセット等の構想あり。実装未完了。

### Phase 4：ペアリング — 0%

構想あり。実装未完了。

### Phase 5：ログ管理 — 20%

リアルタイム表示は存在。CSV保存、履歴管理、再読み込み等は当時未完成。

## UI進捗

当時の認識では約85〜90%。

完了・実装済み候補：

- タブ構造
- Mode1（測定）
- Mode2（評価）
- リアルタイムグラフ

未完了・後回し候補：

- グラフ2軸化
- ログ連携
- Mode3〜5

## バージョン変遷

- Rev1〜Rev5：基本通信、センサ取得テスト、PWM試験。基礎構築。
- Rev6〜Rev8：制御ロジック、データフォーマット、UI連携。システム成立。
- Rev9：測定ツールとして実機測定可能な状態。UI安定、データ取得可能。旧時点ではCSV保存が最大の未解決課題。
- Rev10：CSV比較、ランキング、グラフ重ね表示などの分析ツール化構想。

## 旧評価思想から優先的にサルベージするもの

### Battery個体

- battery_id
- label
- group
- notes
- created_at

### Measurement Features

- average voltage
- average current
- capacity
- voltage drop
- stability
- internal resistance（必要に応じて再設計）
- stop reason

### Performance Features

- Speed
- Power
- Stamina
- Stability
- Growth

### State / Life Stage

Batteryを単一スコアではなく、状態・ライフステージとして扱う思想を維持候補とする。

旧コードの閾値はそのまま現行仕様とはしない。

### Recommendation

測定・分析結果を、以下のようなユーザー行動へ結び付ける思想を維持候補とする。

- 充電
- 休止
- 実戦投入
- 練習用途
- 育成
- ペアリング
- 引退候補

### Pairing

2本のBatteryについて、容量差、内部抵抗差、Speed / Power / Stamina / Stability / Growth等を組み合わせ、用途別のペア適性を評価する構想が存在した。

### Usage Model

用途として、短距離・スプリント、バランス、長距離・スタミナ等へ適性を分ける思想をサルベージ候補とする。

## 現行システムへの統合方針

旧システム：

```text
Battery Device -> UI -> Evaluation
```

から、現行では以下の分離を基本候補とする。

```text
Battery Device
    -> Measurement
    -> Feature Extraction
    -> Battery Analysis
    -> Battery Performance Model
    -> Database / UI / Simulator
```

測定値と評価結果を分離する。

シミュレーター統合以前の旧設計なので、Battery AnalysisとSimulator Modelを直接結合しない。

## サルベージ判定

| 資産 | 方針 |
|---|---|
| 旧評価思想 | 積極的にサルベージ |
| Battery状態・ライフステージ | サルベージして再設計 |
| 推奨行動 | サルベージ |
| Growth / 育成思想 | サルベージ候補 |
| スコアリング思想 | サルベージして再設計 |
| DB項目 | 現行DBと照合して再利用 |
| CSV項目 | 現行Measurement仕様と照合 |
| 旧UI | 表現・要求機能の参考 |
| 旧Arduinoコード | 現行2ch実装を優先し、必要な考え方のみ回収 |
| 旧配線 | 採用しない |
| 旧実測ログ値 | 性能根拠にはしない |

## 設計統合役への要求

1. 旧 `battery/` をBattery評価システムの知識ベースとして扱う。
2. 現行2ch Deviceをハードウェアの正とする。
3. 旧評価思想を現行Battery System仕様へ再マッピングする。
4. Measurement / Feature Extraction / Analysis / Performance Modelを分離する。
5. 現行DB設計と照合する。
6. シミュレーターへ渡すBattery Performance Modelを定義する。
7. 旧コードを直接復活させるのではなく、必要なアルゴリズムのみ回収する。

## 現時点の総括

過去開発は「何も完成しなかった」のではない。少なくとも当時の認識では、計測・制御は完成し、評価ロジックも90〜95%程度まで到達していた。旧開発の残課題はログ管理、育成、ペアリング、分析機能などだった。

現在は新しい2ch Deviceを完成品として扱い、旧 `battery/` の評価思想をサルベージし、現在のDB・Analysis Engine・Simulator設計へ統合する。

最終目標は、

```text
測定 -> 保存 -> 分析 -> 評価 -> 選別 / 推奨 -> Simulator
```

を一貫して成立させること。
