# Discord OLLAMA Bot ja-JP

これは本プロジェクトの日本語向け補足ドキュメントです。

このプロジェクトは、高校時代に作成した Discord Bot を整理して公開した学習用プロジェクトです。Discord サーバー管理、ローカル Ollama AI、モデレーション案件の報告、ユーザーとのやり取りの要約、PC 状態監視、温度保護、個人用音楽ライブラリなどを組み合わせています。

> **翻訳について**  
> 本プロジェクトは、実際のソースコードと英語の GitHub 向け主要文書を最終的な基準とします。日本語文書は AI による翻訳・整理を含む場合があり、内容に差異がある場合はソースコードを優先してください。

## AI Provider and Privacy Notice

This project was originally designed to use local Ollama as the main AI provider.

When privacy is important, using a local AI model is recommended because prompts, moderation context, user interaction summaries, memory-related data, and logs can remain on the deployer's own machine.

If the deployer modifies this project to use a cloud AI API, prompts, user-related context, moderation records, or conversation data may be sent to a third-party provider.

If you choose to use a cloud AI API, you are responsible for reviewing the provider's privacy policy, data retention policy, terms of service, and any legal or compliance requirements.

For privacy-sensitive servers, school environments, or communities involving minors, local AI deployment is strongly recommended.


## ドキュメント入口

- [コマンド概要](./COMMANDS.md)
- [AI とモデレーション機能の説明](./AI_AND_MODERATION_NOTES.md)
- [docs 総合入口へ戻る](../README.md)

## プロジェクトの位置づけ

このリポジトリは主に以下の目的で公開されています。

- 学習記録
- ポートフォリオ
- 教育・授業での参考資料
- Discord Bot とローカル AI の統合例

特別な理由がない限り、このプロジェクトに大きな更新が入る可能性は高くありません。

## 安全上の注意

`.env`、Discord Bot Token、Webhook URL、API Key、パスワード、`data/`、`logs/`、AI 会話記録、ユーザー情報、モデレーション案件、音楽ファイルを公開しないでください。

もし token、API key、webhook、パスワードなどが公開された場合は、すぐに無効化または再生成してください。

## ライセンス上の注意

学習、授業、個人練習、教育参考、学術参考としての利用は歓迎します。商用利用、無断再配布、個人データの悪用、データ販売、権利のない音楽や著作権コンテンツの利用は禁止されています。
