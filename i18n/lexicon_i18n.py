#!/usr/bin/env python3
"""lexicon_i18n.py — agimem 多语言子层（H5）的人工词库。

设计约束（对应 tests/33-multilingual.md 与出题铁律 cdf155a9）：
- 每条 fact 是一个**真实工程场景**的教训：部署 / 对接 / 交接 / 排障，禁用科幻、纯数学、纯图案。
- 四种语言（zh/en/ja/es）**人工写死**，逐条语义对齐；不做机翻，避免翻译噪音当题。
- 题的 gold 与语言无关：每条 fact 的 fid 固定，四种语言的题面都指向同一 fid。
- 题面用问句，记忆条目用陈述句，避免题面与条目逐字重合造成词面假命中。

规模：24 条 fact × 4 语言 = 96 条平行题面；写入侧也按需复用同一批文本。
"""

from __future__ import annotations

LANGS = ("zh", "en", "ja", "es")

DOMAINS = ("deploy", "integration", "handover", "troubleshooting")

# 24 条真实场景：6 部署 / 6 对接 / 6 交接 / 6 排障
FACTS = [
    # ---------------------------------------------------------------- deploy
    {
        "fid": "mlf0001", "domain": "deploy",
        "title": {
            "zh": "灰度切 5% 后 500 率升高先回滚",
            "en": "Roll back first when the 5% canary raises the 500 rate",
            "ja": "カナリア5%で500率上昇なら先にロールバック",
            "es": "Con el 5% en canario, si sube el 500, primero revertir",
        },
        "body": {
            "zh": "灰度把流量切到 5% 后 500 率从 0.1% 升到 3%，先回滚到上一版本，再用日志定位，不要在线上继续加流量。",
            "en": "After routing 5% of traffic to the canary the 500 rate rose from 0.1% to 3%; roll back to the previous version first and locate the cause from logs instead of sending more traffic.",
            "ja": "カナリアに5%のトラフィックを流したら500率が0.1%から3%へ上がった。まず前バージョンへロールバックし、ログで原因を特定する。流量は増やさない。",
            "es": "Tras enviar el 5% del tráfico al canario, la tasa de 500 subió de 0,1% a 3%; primero se revierte a la versión anterior y se buscan las causas en los registros, sin mandar más tráfico.",
        },
        "query": {
            "zh": "灰度发布切了 5% 流量，500 率突然升高，第一步该做什么？",
            "en": "We sent 5% of traffic to the canary and the 500 rate jumped; what is the first step?",
            "ja": "カナリアに5%流したら500率が急上昇しました。最初に何をすべきですか？",
            "es": "Enviamos el 5% del tráfico al canario y la tasa de 500 subió; ¿cuál es el primer paso?",
        },
    },
    {
        "fid": "mlf0002", "domain": "deploy",
        "title": {
            "zh": "滚动发布先到一半再切流量",
            "en": "Roll out to half the instances before switching traffic",
            "ja": "ローリング更新は半分まで進めてから流量を切る",
            "es": "Despliega a la mitad de las instancias antes de cambiar el tráfico",
        },
        "body": {
            "zh": "滚动发布不要一次全推，先滚动到一半实例，确认健康检查通过再切流量，出问题只影响一半容量。",
            "en": "Do not push a rolling update to every instance at once: roll to half, confirm health checks pass, then switch traffic so a failure only costs half the capacity.",
            "ja": "ローリング更新で一度に全部へ配信しない。半分のインスタンスまで進め、ヘルスチェック通過を確認してから流量を切り替える。",
            "es": "No apliques la actualización gradual a todas las instancias a la vez: llega a la mitad, confirma que pasan las comprobaciones de salud y luego cambia el tráfico.",
        },
        "query": {
            "zh": "滚动发布怎么配置才能避免一次性全挂？",
            "en": "How should a rolling deployment be staged so a single failure cannot take everything down?",
            "ja": "ローリング更新で全台同時に落ちないようにするにはどう段階化しますか？",
            "es": "¿Cómo se debe escalonar un despliegue gradual para que un fallo no tumbe todo?",
        },
    },
    {
        "fid": "mlf0003", "domain": "deploy",
        "title": {
            "zh": "大表加字段先加列后回填",
            "en": "Add a nullable column first, backfill in batches",
            "ja": "大きな表には先にNULL許可列を足してから分割で埋める",
            "es": "Añade primero una columna anulable y rellena por lotes",
        },
        "body": {
            "zh": "大表加字段要走先加可空列、再分批回填、最后加约束三步，直接改表会长时间锁表。",
            "en": "On a large table add the nullable column first, backfill in batches, then add constraints; altering the table in one step locks it for a long time.",
            "ja": "大きな表の列追加は、NULL許可列の追加、分割バックフィル、制約追加の三段階で行う。一度に変更すると長時間ロックされる。",
            "es": "En una tabla grande, añade la columna anulable, rellena por lotes y solo después añade las restricciones; hacerlo de una vez bloquea la tabla mucho tiempo.",
        },
        "query": {
            "zh": "给大表加字段怎样避免长时间锁表？",
            "en": "How do we add a column to a large table without locking it for a long time?",
            "ja": "大きな表に列を追加するとき、長時間のロックを避けるには？",
            "es": "¿Cómo añadimos una columna a una tabla grande sin bloquearla mucho tiempo?",
        },
    },
    {
        "fid": "mlf0004", "domain": "deploy",
        "title": {
            "zh": "回滚要连配置一起回滚",
            "en": "Roll back configuration together with the image",
            "ja": "ロールバックは設定も一緒に戻す",
            "es": "Revierte también la configuración, no solo la imagen",
        },
        "body": {
            "zh": "只回滚镜像不回滚配置，旧版本读不懂新配置字段会启动失败，回滚必须镜像与配置成对。",
            "en": "Rolling back only the image leaves new configuration fields the old build cannot parse, so startup fails; image and configuration must be rolled back as a pair.",
            "ja": "イメージだけ戻すと、旧バージョンが解釈できない新しい設定項目が残り起動に失敗する。イメージと設定は必ず対で戻す。",
            "es": "Revertir solo la imagen deja campos nuevos de configuración que la versión anterior no entiende y el arranque falla; imagen y configuración se revierten juntas.",
        },
        "query": {
            "zh": "回滚镜像后服务反而起不来，可能是什么原因？",
            "en": "After rolling back the image the service will not start; what is the likely cause?",
            "ja": "イメージを戻したらサービスが起動しなくなりました。原因は何でしょう？",
            "es": "Tras revertir la imagen el servicio no arranca; ¿cuál es la causa probable?",
        },
    },
    {
        "fid": "mlf0005", "domain": "deploy",
        "title": {
            "zh": "蓝绿切换前先预热新集群",
            "en": "Warm the new cluster before the blue-green switch",
            "ja": "ブルーグリーン切替の前に新クラスタを温める",
            "es": "Precalienta el clúster nuevo antes del cambio azul-verde",
        },
        "body": {
            "zh": "切到绿集群前先跑健康检查并预热请求，否则冷启动的慢请求会直接暴露给用户。",
            "en": "Before switching to the green cluster run health checks and warm it with requests, otherwise cold-start latency hits users immediately.",
            "ja": "グリーンクラスタへ切り替える前にヘルスチェックとウォームアップ要求を流す。そうしないとコールドスタートの遅延が利用者にそのまま出る。",
            "es": "Antes de pasar al clúster verde ejecuta comprobaciones de salud y caliéntalo con peticiones; si no, la latencia de arranque en frío llega al usuario.",
        },
        "query": {
            "zh": "蓝绿发布切换前需要做哪些准备？",
            "en": "What preparation is needed before a blue-green cutover?",
            "ja": "ブルーグリーン切替の前に何を準備すべきですか？",
            "es": "¿Qué preparación hace falta antes de un cambio azul-verde?",
        },
    },
    {
        "fid": "mlf0006", "domain": "deploy",
        "title": {
            "zh": "服务用 systemd 托管别用 nohup",
            "en": "Run the service under systemd, not nohup",
            "ja": "サービスはsystemdで管理しnohupを使わない",
            "es": "Gestiona el servicio con systemd, no con nohup",
        },
        "body": {
            "zh": "nohup 起的进程机器一重启就没了，服务要交给 systemd 托管并设开机自启。",
            "en": "A process started with nohup disappears when the machine reboots; run the service under systemd with autostart enabled.",
            "ja": "nohupで起動したプロセスは再起動で消える。systemdで管理し自動起動を有効にする。",
            "es": "Un proceso lanzado con nohup desaparece al reiniciar la máquina; gestiona el servicio con systemd y activa el arranque automático.",
        },
        "query": {
            "zh": "机器重启后服务就没了，该怎么托管？",
            "en": "The service disappears after a reboot; how should it be managed?",
            "ja": "再起動するとサービスが消えます。どう管理すべきですか？",
            "es": "El servicio desaparece tras reiniciar; ¿cómo debe gestionarse?",
        },
    },
    # ----------------------------------------------------------- integration
    {
        "fid": "mlf0007", "domain": "integration",
        "title": {
            "zh": "回调验签失败先查时间戳偏差",
            "en": "Callback signature failures start with clock skew",
            "ja": "コールバック署名失敗はまず時刻ずれを疑う",
            "es": "Si falla la firma del callback, revisa primero el desfase de reloj",
        },
        "body": {
            "zh": "支付回调验签失败多是对齐时间戳超出五分钟窗口，先校准 NTP 再排查签名串拼接。",
            "en": "Payment callback signature failures are usually a timestamp outside the five-minute window; sync NTP first, then inspect how the signing string is built.",
            "ja": "決済コールバックの署名失敗は、時刻が5分の許容窓を外れていることが多い。まずNTPで時刻を合わせ、その後に署名文字列の組み立てを確認する。",
            "es": "Los fallos de firma en callbacks de pago suelen ser una marca de tiempo fuera de la ventana de cinco minutos; sincroniza NTP y luego revisa cómo se arma la cadena firmada.",
        },
        "query": {
            "zh": "第三方支付回调一直验签失败，先查什么？",
            "en": "Payment callbacks keep failing signature verification; what do we check first?",
            "ja": "決済コールバックの署名検証が通りません。まず何を確認しますか？",
            "es": "Los callbacks de pago no pasan la verificación de firma; ¿qué revisamos primero?",
        },
    },
    {
        "fid": "mlf0008", "domain": "integration",
        "title": {
            "zh": "短信模板 ID 与签名必须成对",
            "en": "SMS template ID and signature must match as a pair",
            "ja": "SMSのテンプレートIDと署名は対で一致させる",
            "es": "El ID de plantilla SMS y la firma deben coincidir en pareja",
        },
        "body": {
            "zh": "短信网关返回 400 常见原因是模板 ID 与签名不匹配，两者要一起申请、一起修改。",
            "en": "A 400 from the SMS gateway is often a template ID that does not match the signature; apply for and change both together.",
            "ja": "SMSゲートウェイの400は、テンプレートIDと署名の不一致がよくある原因。両方を同時に申請し、同時に変更する。",
            "es": "Un 400 del gateway SMS suele ser un ID de plantilla que no coincide con la firma; solicita y cambia ambos a la vez.",
        },
        "query": {
            "zh": "短信接口返回 400，常见原因是什么？",
            "en": "The SMS API returns 400; what is the usual cause?",
            "ja": "SMS APIが400を返します。よくある原因は？",
            "es": "La API de SMS devuelve 400; ¿cuál es la causa habitual?",
        },
    },
    {
        "fid": "mlf0009", "domain": "integration",
        "title": {
            "zh": "OAuth 回调地址要与白名单逐字一致",
            "en": "OAuth redirect URI must match the allowlist exactly",
            "ja": "OAuthのリダイレクトURIは許可リストと完全一致させる",
            "es": "La URI de redirección OAuth debe coincidir exactamente con la lista blanca",
        },
        "body": {
            "zh": "回调地址末尾多一个斜杠或 http 与 https 不同都会跳转失败，必须与后台白名单逐字符一致。",
            "en": "An extra trailing slash or an http/https mismatch makes the redirect fail; the URI must match the allowlist character for character.",
            "ja": "末尾のスラッシュが余分だったりhttpとhttpsが違うとリダイレクトに失敗する。許可リストと1文字単位で一致させる。",
            "es": "Una barra final de más o un http frente a https hace fallar la redirección; la URI debe coincidir carácter a carácter con la lista blanca.",
        },
        "query": {
            "zh": "OAuth 授权后跳转失败，该检查哪里？",
            "en": "After OAuth authorization the redirect fails; where do we look?",
            "ja": "OAuth認可後のリダイレクトが失敗します。どこを確認しますか？",
            "es": "Tras autorizar OAuth la redirección falla; ¿dónde miramos?",
        },
    },
    {
        "fid": "mlf0010", "domain": "integration",
        "title": {
            "zh": "Webhook 重试按 event id 幂等",
            "en": "Make webhook retries idempotent by event ID",
            "ja": "Webhook再送はevent idで冪等にする",
            "es": "Haz idempotentes los reintentos de webhook por event ID",
        },
        "body": {
            "zh": "对方超时会重推同一 event id，消费端必须按 event id 去重，否则会重复扣款。",
            "en": "On timeout the sender retries the same event ID, so the consumer must deduplicate by event ID or it charges twice.",
            "ja": "タイムアウト時は同じevent idが再送されるため、受信側はevent idで重複排除しないと二重課金になる。",
            "es": "Si hay timeout, el emisor reintenta el mismo event ID; el consumidor debe deduplicar por event ID o cobra dos veces.",
        },
        "query": {
            "zh": "Webhook 重复推送怎样防止重复处理？",
            "en": "How do we stop duplicate webhook deliveries from being processed twice?",
            "ja": "Webhookの重複配信を二重処理しないようにするには？",
            "es": "¿Cómo evitamos procesar dos veces entregas duplicadas de webhook?",
        },
    },
    {
        "fid": "mlf0011", "domain": "integration",
        "title": {
            "zh": "跨域预检要放行 PUT 与自定义头",
            "en": "Allow PUT and custom headers in the CORS preflight",
            "ja": "CORSプリフライトでPUTと独自ヘッダを許可する",
            "es": "Permite PUT y cabeceras propias en el preflight CORS",
        },
        "body": {
            "zh": "浏览器直传对象存储前会发 OPTIONS 预检，CORS 规则不放行 PUT 或自定义头就会失败。",
            "en": "Browser uploads to object storage send an OPTIONS preflight first; if CORS does not allow PUT or the custom header the upload fails.",
            "ja": "ブラウザからオブジェクトストレージへ直接アップロードする前にOPTIONSのプリフライトが飛ぶ。CORSでPUTや独自ヘッダを許可しないと失敗する。",
            "es": "Las subidas del navegador al almacenamiento de objetos envían primero un preflight OPTIONS; si CORS no permite PUT o la cabecera propia, falla.",
        },
        "query": {
            "zh": "前端直传对象存储报跨域错误，CORS 怎么配？",
            "en": "Direct browser uploads to object storage hit a CORS error; how should CORS be configured?",
            "ja": "ブラウザから直接アップロードするとCORSエラーになります。どう設定しますか？",
            "es": "Las subidas directas del navegador dan error CORS; ¿cómo se configura?",
        },
    },
    {
        "fid": "mlf0012", "domain": "integration",
        "title": {
            "zh": "位点在业务成功后再提交",
            "en": "Commit the consumer offset after the business succeeds",
            "ja": "オフセットは業務成功後にコミットする",
            "es": "Confirma el offset después de que el negocio tenga éxito",
        },
        "body": {
            "zh": "先提交位点再处理业务，进程崩溃就会丢消息；要在业务成功之后再提交位点。",
            "en": "Committing the offset before processing means a crash loses the message; commit only after the business step succeeds.",
            "ja": "オフセットを先にコミットしてから処理すると、プロセスが落ちたときにメッセージを失う。業務成功後にコミットする。",
            "es": "Confirmar el offset antes de procesar hace que un fallo pierda el mensaje; confirma solo cuando el negocio termine bien.",
        },
        "query": {
            "zh": "消息队列消费偶尔丢消息，可能是什么原因？",
            "en": "The message queue consumer occasionally loses messages; what could cause that?",
            "ja": "メッセージキューの消費でときどきメッセージを失います。原因は？",
            "es": "El consumidor de la cola pierde mensajes de vez en cuando; ¿a qué se debe?",
        },
    },
    # -------------------------------------------------------------- handover
    {
        "fid": "mlf0013", "domain": "handover",
        "title": {
            "zh": "交接单第一项写发布冻结期",
            "en": "Put the release freeze window first on the handover sheet",
            "ja": "引き継ぎ書の最初にリリース凍結期間を書く",
            "es": "Pon primero la ventana de congelación de despliegues en el traspaso",
        },
        "body": {
            "zh": "交接单第一项写清本周发布冻结窗口与例外审批人，避免接手人误发布。",
            "en": "Start the handover sheet with this week's release freeze window and who can approve exceptions so the next on-call does not deploy by mistake.",
            "ja": "引き継ぎ書の最初に、今週のリリース凍結期間と例外承認者を明記し、引き継いだ人が誤って配信しないようにする。",
            "es": "Empieza el traspaso con la ventana de congelación de esta semana y quién aprueba excepciones, para que quien entra no despliegue por error.",
        },
        "query": {
            "zh": "值班交接单要写明哪些关键信息？",
            "en": "What key information belongs on an on-call handover sheet?",
            "ja": "当番の引き継ぎ書には何を書くべきですか？",
            "es": "¿Qué información clave debe llevar un traspaso de guardia?",
        },
    },
    {
        "fid": "mlf0014", "domain": "handover",
        "title": {
            "zh": "交接写清证书到期与续期脚本位置",
            "en": "Record certificate expiry and where the renewal script lives",
            "ja": "証明書の期限と更新スクリプトの場所を引き継ぐ",
            "es": "Anota la caducidad del certificado y dónde está el script de renovación",
        },
        "body": {
            "zh": "交接要注明证书到期日、续期脚本路径以及自动续期是否开启，避免到期当天才发现。",
            "en": "Note the certificate expiry date, the path of the renewal script and whether auto-renewal is on, so nobody discovers it on expiry day.",
            "ja": "証明書の有効期限、更新スクリプトのパス、自動更新の有無を引き継ぐ。期限当日に気づく事態を避ける。",
            "es": "Anota la fecha de caducidad, la ruta del script de renovación y si la renovación automática está activa, para no enterarse el día que caduca.",
        },
        "query": {
            "zh": "证书快到期了，交接时要交代什么？",
            "en": "A certificate is about to expire; what must the handover cover?",
            "ja": "証明書の期限が近いです。引き継ぎで何を伝えますか？",
            "es": "Un certificado está por caducar; ¿qué debe cubrir el traspaso?",
        },
    },
    {
        "fid": "mlf0015", "domain": "handover",
        "title": {
            "zh": "灰度开关的配置中心键名要交接",
            "en": "Hand over the config-center key for the canary switch",
            "ja": "カナリアスイッチの設定センターのキー名を引き継ぐ",
            "es": "Traspasa la clave del centro de configuración del interruptor canario",
        },
        "body": {
            "zh": "灰度开关在配置中心，键名 release.canary，改值即可生效，交接必须写清键名与取值范围。",
            "en": "The canary switch lives in the config center under the key release.canary and takes effect on change; the handover must state the key and its allowed values.",
            "ja": "カナリアスイッチは設定センターのrelease.canaryというキーにあり、値を変えれば反映される。キー名と取り得る値を引き継ぐ。",
            "es": "El interruptor canario está en el centro de configuración con la clave release.canary y surte efecto al cambiarla; el traspaso debe indicar clave y valores admitidos.",
        },
        "query": {
            "zh": "灰度开关在哪里改，交接怎么写？",
            "en": "Where is the canary switch changed, and how should the handover describe it?",
            "ja": "カナリアスイッチはどこで変更しますか。引き継ぎにはどう書きますか？",
            "es": "¿Dónde se cambia el interruptor canario y cómo se describe en el traspaso?",
        },
    },
    {
        "fid": "mlf0016", "domain": "handover",
        "title": {
            "zh": "值班手机与升级路径写第一页",
            "en": "On-call phone and escalation path go on page one",
            "ja": "当番携帯とエスカレーション経路を1ページ目に書く",
            "es": "Teléfono de guardia y ruta de escalado en la primera página",
        },
        "body": {
            "zh": "交接单第一页写值班手机、二线负责人和升级路径，夜间出问题先按路径升级再排查。",
            "en": "Page one carries the on-call phone, the second-line owner and the escalation path; at night escalate first, then investigate.",
            "ja": "1ページ目に当番携帯、二次担当者、エスカレーション経路を書く。夜間の障害はまず経路どおりに上げてから調査する。",
            "es": "La primera página lleva el teléfono de guardia, el responsable de segundo nivel y la ruta de escalado; de noche se escala primero y luego se investiga.",
        },
        "query": {
            "zh": "夜间告警该找谁，交接单怎么写？",
            "en": "Who do we call for a night alert, and how is that written in the handover?",
            "ja": "夜間のアラートは誰に連絡しますか。引き継ぎ書にはどう書きますか？",
            "es": "¿A quién llamamos ante una alerta nocturna y cómo se recoge en el traspaso?",
        },
    },
    {
        "fid": "mlf0017", "domain": "handover",
        "title": {
            "zh": "夜间批处理窗口不要重启服务",
            "en": "Do not restart services during the nightly batch window",
            "ja": "夜間バッチの時間帯にサービスを再起動しない",
            "es": "No reinicies servicios durante la ventana del proceso nocturno",
        },
        "body": {
            "zh": "批处理每天 02:00 跑，这个窗口重启会中断任务；重启要避开窗口或先停调度。",
            "en": "The batch job runs at 02:00 daily; a restart in that window interrupts it, so either avoid the window or pause the scheduler first.",
            "ja": "バッチは毎日02:00に走る。その時間帯の再起動は処理を中断するので、時間を外すかスケジューラを止めてから再起動する。",
            "es": "El proceso por lotes corre a las 02:00 cada día; un reinicio en esa ventana lo interrumpe, así que evita la ventana o pausa el planificador.",
        },
        "query": {
            "zh": "什么时间段不能重启服务？",
            "en": "During what time window must services not be restarted?",
            "ja": "どの時間帯にサービスを再起動してはいけませんか？",
            "es": "¿En qué franja horaria no se deben reiniciar los servicios?",
        },
    },
    {
        "fid": "mlf0018", "domain": "handover",
        "title": {
            "zh": "维护窗口静默规则会自动开启",
            "en": "The maintenance window silences alerts automatically",
            "ja": "保守時間帯はアラート抑制が自動で有効になる",
            "es": "La ventana de mantenimiento silencia alertas automáticamente",
        },
        "body": {
            "zh": "每周三维护窗口告警静默规则自动开启，那时段没告警不是监控失灵。",
            "en": "Every Wednesday the maintenance window turns alert silencing on automatically, so quiet alerts in that slot are not a monitoring failure.",
            "ja": "毎週水曜の保守時間帯はアラート抑制が自動で有効になる。その時間に鳴らないのは監視障害ではない。",
            "es": "Cada miércoles la ventana de mantenimiento activa el silenciado de alertas; que no suene nada en esa franja no es un fallo de monitorización.",
        },
        "query": {
            "zh": "周三告警突然不响了，是监控坏了吗？",
            "en": "Alerts went silent on Wednesday; is monitoring broken?",
            "ja": "水曜にアラートが急に鳴らなくなりました。監視障害ですか？",
            "es": "El miércoles las alertas dejaron de sonar; ¿está roto el monitoreo?",
        },
    },
    # --------------------------------------------------------- troubleshooting
    {
        "fid": "mlf0019", "domain": "troubleshooting",
        "title": {
            "zh": "缓存雪崩加随机 TTL 并预热",
            "en": "Beat cache avalanche with jittered TTL and warm-up",
            "ja": "キャッシュ雪崩はTTLのゆらぎとウォームアップで防ぐ",
            "es": "Evita la avalancha de caché con TTL aleatorio y precalentado",
        },
        "body": {
            "zh": "批量 key 用同一 TTL 同时过期会把数据库打满，改成基础 TTL 加随机抖动并预热热点 key。",
            "en": "Many keys sharing one TTL expire together and flood the database; add random jitter to a base TTL and pre-warm hot keys.",
            "ja": "多数のキーが同じTTLで一斉に期限切れになりDBが飽和する。基本TTLにランダムなゆらぎを足し、ホットキーを温める。",
            "es": "Muchas claves con el mismo TTL caducan a la vez y saturan la base de datos; añade fluctuación aleatoria al TTL base y precalienta las claves calientes.",
        },
        "query": {
            "zh": "大量缓存同时过期把数据库打挂了，怎么改？",
            "en": "A mass cache expiry took the database down; how do we fix it?",
            "ja": "大量のキャッシュが同時に期限切れになりDBが落ちました。どう直しますか？",
            "es": "Una caducidad masiva de caché tumbó la base de datos; ¿cómo lo arreglamos?",
        },
    },
    {
        "fid": "mlf0020", "domain": "troubleshooting",
        "title": {
            "zh": "连接池耗尽根因是慢查询",
            "en": "Pool exhaustion usually traces back to slow queries",
            "ja": "コネクションプール枯渇の原因はスロークエリ",
            "es": "El agotamiento del pool suele venir de consultas lentas",
        },
        "body": {
            "zh": "接口超时是连接池耗尽，根因是慢查询占住连接，调大池子只缓解，必须加索引并设查询超时。",
            "en": "API timeouts come from an exhausted pool; the root cause is slow queries holding connections, so enlarge nothing until you add indexes and set a query timeout.",
            "ja": "APIタイムアウトはコネクションプール枯渇が原因で、根本原因はスロークエリが接続を占有していること。プールを増やすだけでは緩和にしかならず、索引とクエリタイムアウトが必要。",
            "es": "Los timeouts de la API vienen de un pool agotado; la causa raíz son consultas lentas que retienen conexiones, así que añade índices y un timeout de consulta en lugar de agrandar el pool.",
        },
        "query": {
            "zh": "接口超时而且连接池满了，根因在哪？",
            "en": "APIs time out and the connection pool is full; where is the root cause?",
            "ja": "APIがタイムアウトし接続プールも満杯です。根本原因はどこですか？",
            "es": "Las API dan timeout y el pool está lleno; ¿dónde está la causa raíz?",
        },
    },
    {
        "fid": "mlf0021", "domain": "troubleshooting",
        "title": {
            "zh": "磁盘写不进先看 inode 不是容量",
            "en": "Cannot write to disk: check inodes before capacity",
            "ja": "ディスクに書けないときは容量より先にinodeを見る",
            "es": "Si no se puede escribir en disco, mira inodos antes que capacidad",
        },
        "body": {
            "zh": "df 显示还有空间却写不进文件，是 inode 被大量小日志文件占满，清理旧日志即可。",
            "en": "df shows free space yet writes fail because inodes are exhausted by many small log files; clean up old logs.",
            "ja": "dfでは空きがあるのに書き込めないのは、小さなログファイルでinodeが枯渇しているため。古いログを削除する。",
            "es": "df muestra espacio libre pero la escritura falla porque muchos archivos de log pequeños agotan los inodos; limpia los logs antiguos.",
        },
        "query": {
            "zh": "磁盘还有空间但写不进文件，查什么？",
            "en": "The disk has free space but writes fail; what do we check?",
            "ja": "ディスクに空きはあるのに書き込めません。何を調べますか？",
            "es": "El disco tiene espacio libre pero falla la escritura; ¿qué revisamos?",
        },
    },
    {
        "fid": "mlf0022", "domain": "troubleshooting",
        "title": {
            "zh": "Nginx 502 先查 upstream 连接",
            "en": "For Nginx 502 check the upstream connection",
            "ja": "Nginxの502はまずupstream接続を調べる",
            "es": "Ante un 502 de Nginx revisa la conexión upstream",
        },
        "body": {
            "zh": "502 多是 upstream 连接被重置，检查 keepalive 配置与后端超时是否匹配。",
            "en": "A 502 is usually a reset upstream connection; check that the keepalive settings and the backend timeouts agree.",
            "ja": "502はupstream接続がリセットされていることが多い。keepalive設定とバックエンドのタイムアウトが整合しているか確認する。",
            "es": "Un 502 suele ser una conexión upstream reiniciada; comprueba que keepalive y los timeouts del backend encajen.",
        },
        "query": {
            "zh": "Nginx 返回 502，先查哪里？",
            "en": "Nginx returns 502; where do we look first?",
            "ja": "Nginxが502を返します。まずどこを見ますか？",
            "es": "Nginx devuelve 502; ¿dónde miramos primero?",
        },
    },
    {
        "fid": "mlf0023", "domain": "troubleshooting",
        "title": {
            "zh": "容器 OOM 给 JVM 设堆上限",
            "en": "Set a JVM heap cap to avoid container OOM",
            "ja": "コンテナOOMを避けるためJVMのヒープ上限を設定する",
            "es": "Fija un límite de heap en la JVM para evitar OOM del contenedor",
        },
        "body": {
            "zh": "容器里 JVM 不设 -Xmx 会按宿主机内存算堆，被 cgroup 判超限杀掉，设到容器限额的七成。",
            "en": "Without -Xmx the JVM sizes its heap from host memory and the cgroup kills it; set the heap to about seventy percent of the container limit.",
            "ja": "コンテナ内で-Xmxを指定しないとJVMはホストのメモリでヒープを計算し、cgroupに超過と判断されて停止される。コンテナ上限の七割程度に設定する。",
            "es": "Sin -Xmx la JVM calcula el heap con la memoria del host y el cgroup la mata; fija el heap en torno al setenta por ciento del límite del contenedor.",
        },
        "query": {
            "zh": "容器反复 OOM 重启，怎么定位？",
            "en": "The container keeps OOM-restarting; how do we diagnose it?",
            "ja": "コンテナがOOMで再起動を繰り返します。どう切り分けますか？",
            "es": "El contenedor se reinicia por OOM una y otra vez; ¿cómo lo diagnosticamos?",
        },
    },
    {
        "fid": "mlf0024", "domain": "troubleshooting",
        "title": {
            "zh": "切流后旧 IP 还有请求是 DNS 缓存",
            "en": "Old IPs still get traffic after cutover: DNS caching",
            "ja": "切替後も旧IPに要求が来るのはDNSキャッシュ",
            "es": "Tras el cambio siguen llegando peticiones a la IP vieja: caché DNS",
        },
        "body": {
            "zh": "切换后仍有请求打到旧 IP，是客户端或本地 DNS 缓存未过期，降低 TTL 并等缓存过期。",
            "en": "Requests still reach the old IP because client or local DNS caches have not expired; lower the TTL and wait for caches to age out.",
            "ja": "切替後も旧IPに要求が届くのは、クライアントやローカルDNSのキャッシュが期限切れになっていないため。TTLを下げて失効を待つ。",
            "es": "Las peticiones siguen llegando a la IP vieja porque las cachés DNS del cliente o locales no han caducado; baja el TTL y espera a que expiren.",
        },
        "query": {
            "zh": "切流后旧机器还在收请求，为什么？",
            "en": "After the cutover the old host still receives requests; why?",
            "ja": "切替後も旧ホストに要求が来ます。なぜですか？",
            "es": "Tras el cambio el host viejo sigue recibiendo peticiones; ¿por qué?",
        },
    },
]


def fact_ids():
    return [f["fid"] for f in FACTS]


def validate() -> None:
    """词库自检：fid 唯一、四语言齐全、域分布均衡、文本非空且无敏感片段。"""
    ids = fact_ids()
    if len(ids) != len(set(ids)):
        raise SystemExit("lexicon: fid 重复")
    if len(FACTS) != 24:
        raise SystemExit(f"lexicon: 期望 24 条 fact，实际 {len(FACTS)}")
    from collections import Counter
    dom = Counter(f["domain"] for f in FACTS)
    for d in DOMAINS:
        if dom.get(d) != 6:
            raise SystemExit(f"lexicon: 域 {d} 条数 {dom.get(d)} != 6")
    banned = ["sk-", "password", "口令", "api key", "@gmail", "身份证"]
    for f in FACTS:
        for key in ("title", "body", "query"):
            block = f[key]
            if set(block) != set(LANGS):
                raise SystemExit(f"lexicon: {f['fid']} {key} 语言不全: {sorted(block)}")
            for lang in LANGS:
                text = block[lang].strip()
                if not text:
                    raise SystemExit(f"lexicon: {f['fid']} {key}.{lang} 为空")
                for b in banned:
                    if b in text.lower():
                        raise SystemExit(f"lexicon: {f['fid']} {key}.{lang} 命中敏感片段 {b!r}")
    # 题面不得与自身条目文本完全一致（防词面抄近路）
    for f in FACTS:
        for lang in LANGS:
            if f["query"][lang].strip() == f["body"][lang].strip():
                raise SystemExit(f"lexicon: {f['fid']}.{lang} 题面与正文相同")


if __name__ == "__main__":
    validate()
    print(f"lexicon OK: {len(FACTS)} facts x {len(LANGS)} langs = {len(FACTS)*len(LANGS)} 平行题面")
