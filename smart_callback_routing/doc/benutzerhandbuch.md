# Benutzerhandbuch – Smart Callback Routing (3CX)

> Modulversion 19.0.2.0.0 · Odoo 19 (Community oder Enterprise)
>
> Dieses Handbuch richtet sich an Anwender und Administratoren, die das Modul in
> Odoo einrichten und im Alltag überwachen. Die technische Einrichtung der
> Telefonanlage (3CX) ist bewusst nur kompakt beschrieben; die vollständige
> Schritt-für-Schritt-Anleitung dafür steht in
> [`../docs/3cx_cfd/README.md`](../docs/3cx_cfd/README.md) und
> [`../docs/CONFIG_GUIDE.md`](../docs/CONFIG_GUIDE.md).
>
> Die Menü- und Feldbezeichnungen der Oberfläche werden in Odoo Englisch
> ausgeliefert. In diesem Handbuch stehen die deutschen Bezeichnungen mit der
> englischen Originalbeschriftung in Klammern, damit Sie beide im Programm
> wiederfinden.

---

## 1. Wofür ist das Modul?

Ruft ein Kontakt bei Ihnen zurück, soll der Anruf bevorzugt bei genau dem
Kollegen klingeln, der diesen Kontakt zuletzt selbst herausgerufen hat. Odoo
merkt sich dafür nach jedem ausgehenden Anruf für eine begrenzte Zeit eine
Zuordnung „Telefonnummer → Nebenstelle" und liefert sie an die Telefonanlage,
sobald derselbe Kontakt zurückruft. Die Zuordnung ist temporär (TTL, standardmäßig
2 Stunden) und greift nie blockierend ein: Ist niemand zuordenbar, erreichbar oder
tritt ein Fehler auf, läuft der Anruf ganz normal wie bisher über die Warteschlange.

---

## 2. Voraussetzungen

- **Odoo 19** (Community **oder** Enterprise – es werden keine Enterprise-Module
  benötigt).
- Das installierte Modul **Smart Callback Routing (3CX)**.
- Eine **3CX V20 self-hosted**-Anlage, auf der **Call Processing Scripts**
  (Anrufskripte) verfügbar sind. Auf einer von 3CX gehosteten Anlage kann diese
  Skript-Option deaktiviert sein.
- Das gemeinsame **3CX-CRM-Template** (`3cx_odoo_v20.xml`) für die Erfassung der
  ausgehenden Anrufe (Call Journaling).

> Ohne die 3CX-Seite (Abschnitt 6) entstehen keine Zuordnungen und es wird nichts
> geroutet – Odoo ist nur die eine Hälfte der Lösung.

---

## 3. Ersteinrichtung in Odoo

**Ziel:** Die Routing-API scharfschalten, damit 3CX mit Odoo sprechen darf, und
das Grundverhalten festlegen.

**Voraussetzung:** Sie sind als **Manager** (Gruppe *Manager*, siehe Abschnitt 9)
angemeldet – nur diese Gruppe sieht die Einstellungen.

**Schritte:**

1. Öffnen Sie **Callback Routing → Konfiguration → Einstellungen**
   (*Callback Routing → Configuration → Settings*). Alternativ: **Einstellungen**
   öffnen und links den Bereich **Smart Callback Routing** wählen.
2. Klicken Sie im Block **API-Sicherheit** (*API Security*) neben
   **API-Schlüssel** (*API key*) auf **Neuen Schlüssel erzeugen**
   (*Generate new key*). Odoo legt einen zufälligen Schlüssel an und speichert ihn.
3. Kopieren Sie den erzeugten Schlüssel (Kopier-Symbol am Feld) – Sie tragen ihn
   später auf der 3CX-Seite ein.
4. Prüfen bzw. setzen Sie im Block **Routing-Verhalten** (*Routing Behavior*):
   - **Sticky-Gültigkeitsdauer (Minuten)** (*Sticky TTL (minutes)*) – wie lange
     eine Zuordnung gilt. Standard: `120` (2 Stunden).
   - **Erst-Klingel-Timeout (Sekunden)** (*First-ring timeout (seconds)*) – wie
     lange die bevorzugte Nebenstelle allein klingelt, bevor die Warteschlange
     übernimmt. Standard: `12`. (Hinweis: siehe Abschnitt 6 – dieser Wert wird von
     der 3CX-Nebenstelle durchgesetzt, nicht von Odoo.)
   - **Standard-Ländervorwahl** (*Default country prefix*) – Vorwahl ohne „+", die
     bei nationalen Nummern (führende 0) ergänzt wird. Deutschland = `49`.
5. Optional im Block **Verfügbarkeit (Überspringen-Regeln)**
   (*Availability (Skip Rules)*): **Besetzt / Offline / DND überspringen**
   (*Skip busy / offline / DND extension*). Diese Regeln wirken **nur**, wenn 3CX
   den Presence-Status der Nebenstellen an Odoo meldet. Ohne diese Meldung gilt
   jede Nebenstelle als verfügbar – der Klingel-Timeout fängt den nicht
   erreichbaren Fall ohnehin ab.
6. Optional im Block **API-Sicherheit**: **HMAC-Signaturgeheimnis (optional)**
   (*HMAC signing secret (optional)*). Lassen Sie das Feld **leer**, wenn Sie das
   Anrufskript in 3CX verwenden – im Skript-Sandkasten ist eine HMAC-Signatur
   nicht möglich; der API-Schlüssel genügt.
7. **Speichern** Sie die Einstellungen oben in der Leiste.

**Ergebnis:** Die API ist aktiv. Ohne gesetzten API-Schlüssel weist Odoo jede
Anfrage mit „401 – nicht autorisiert" ab; die Einrichtung ist also erst mit
Schritt 2 abgeschlossen.

**Hinweise:**

- Der **API-Schlüssel** liegt im Klartext in der Datenbank und wird bei
  Datenbank-Kopien mitgenommen. Erzeugen Sie ihn nach Bedarf neu und tragen Sie
  ihn dann in 3CX erneut ein.
- Der Block **Protokollierung** (*Logging*) mit **Routing-Entscheidungen
  protokollieren** (*Log routing decisions*) ist standardmäßig an und speist das
  Routing-Protokoll (Abschnitt 5). Für maximale Performance lässt er sich
  abschalten – dann fehlen aber die Einträge zur Nachvollziehbarkeit.

---

## 4. Der Not-Aus: „Sticky-Routing pausieren"

**Ziel:** Das bevorzugte Klingeln vorübergehend komplett abschalten, ohne an der
Telefonanlage etwas zu ändern.

**Voraussetzung:** Manager-Rechte (siehe Abschnitt 9).

**Was der Not-Aus tut:** Ist der Schalter **Sticky-Routing pausieren (Not-Aus)**
(*Pause sticky routing (kill switch)*) aktiv, antwortet die Routing-API bei jedem
Rückruf mit „Standard-Routing". 3CX leitet dann überall ganz normal weiter, so als
wäre das Modul nicht vorhanden. Ausgehende Anrufe werden weiterhin als Zuordnung
erfasst – nur die bevorzugte Weiterleitung beim Rückruf entfällt. Der Schalter
wirkt serverseitig und **sofort**; an 3CX muss **nichts** umgestellt werden.

**Wann Sie ihn nutzen:** bei Wartung, Urlaub der zugeordneten Kollegen oder einer
Störung, wenn Rückrufe für eine Weile wieder generell über die normale
Warteschlange laufen sollen.

**Schritte:**

1. **Callback Routing → Konfiguration → Einstellungen** öffnen.
2. Im Block **Routing-Verhalten** den Schalter **Sticky-Routing pausieren
   (Not-Aus)** einschalten.
3. **Speichern**.

**Ergebnis:** Ab sofort erhalten alle Rückrufe „Standard-Routing". Im
Routing-Protokoll (Abschnitt 5) erscheinen die betroffenen Anrufe mit der
Entscheidung **Standard-Routing** (*default*) und dem Fallback-Grund **Sticky
pausiert (Not-Aus)** (*Sticky paused (kill switch)*).

**Hinweise:**

- Zum Wieder-Einschalten den Schalter ausschalten und speichern – das bevorzugte
  Klingeln greift dann sofort wieder für alle noch gültigen Zuordnungen.

---

## 5. Tägliche Nutzung und Überwachung

Alle Auswertungen liegen im Menü **Callback Routing**. Die beiden
Überwachungsansichten stehen auch der Gruppe **User** (nur lesend) offen.

### 5.1 Aktive Zuordnungen

**Callback Routing → Aktive Zuordnungen** (*Callback Routing → Active Mappings*)
zeigt die gemerkten Zuordnungen „Telefonnummer → Nebenstelle". Die Liste ist
voreingestellt auf den Filter **Gültig (nicht abgelaufen)** (*Valid (not
expired)*), zeigt also nur aktuell wirksame Zuordnungen.

| Spalte (deutsch / englisch) | Bedeutung |
|---|---|
| **Telefonnummer** (*Phone Number*) | Die normalisierte externe Rufnummer des Kontakts, z. B. `+491701234567`. |
| **Nebenstelle** (*Extension*) | Die 3CX-Nebenstelle des Kollegen, der zuletzt herausgerufen hat. |
| **Erstellt** (*Created*) | Zeitpunkt des ersten Kontakts. Bleibt bei einem erneuten Anruf stehen. |
| **Läuft ab** (*Expires*) | Ende der Gültigkeit (Erstellzeit + Gültigkeitsdauer). Abgelaufene Zuordnungen werden ausgegraut dargestellt. |
| **Aktiv** (*Active*) | Schalter, mit dem sich eine Zuordnung manuell deaktivieren lässt. |

Weitere, standardmäßig ausgeblendete Spalten (über das Spaltenmenü einblendbar):
**Zugeordnete Nebenstelle** (*Mapped Extension* – die verknüpfte
Nebenstellen-Karteikarte, sofern vorhanden) und **Letzte Anruf-ID** (*Last Call
ID* – die 3CX-Anruf-ID des auslösenden Gesprächs).

**Nützliche Filter** (Suchleiste):

- **Aktiv** (*Active*) – alle nicht deaktivierten Zuordnungen.
- **Gültig (nicht abgelaufen)** (*Valid (not expired)*) – nur aktive und noch
  nicht abgelaufene Zuordnungen (Standardansicht).
- Gruppieren nach **Nebenstelle** (*Extension*) oder **Unternehmen** (*Company*).

> Zuordnungen entstehen **automatisch**, sobald 3CX ausgehende Anrufe meldet. Sie
> lassen sich in dieser Ansicht nicht von Hand anlegen.

### 5.2 Routing-Protokoll

**Callback Routing → Routing-Protokoll** (*Callback Routing → Routing Log*)
protokolliert jede Entscheidung und ist Ihr wichtigstes Werkzeug zur
Fehlersuche.

| Spalte (deutsch / englisch) | Bedeutung |
|---|---|
| **Zeitstempel** (*Timestamp*) | Zeitpunkt des Ereignisses. |
| **Ereignis** (*Event*) | Art des Vorgangs: **Ausgehend erfasst** (*Outbound recorded*), **Eingehende Abfrage** (*Inbound lookup*), **Presence-Aktualisierung** (*Presence update*) oder **Fehler** (*Error*). |
| **Telefonnummer** (*Phone Number*) | Die normalisierte Rufnummer. |
| **DID/Warteschlange** (*DID/Queue*) | Angerufene DID bzw. Ziel-Warteschlange aus der Anfrage. |
| **Nebenstelle** (*Extension*) | Betroffene Nebenstelle. |
| **Entscheidung** (*Decision*) | Das Ergebnis (siehe Tabelle unten). |
| **Fallback-Grund** (*Fallback Reason*) | Warum kein bevorzugtes Klingeln erfolgte (siehe Tabelle unten). |
| **Latenz (ms)** (*Latency (ms)*) | Antwortzeit der Abfrage in Millisekunden. |

**Mögliche Entscheidungen** (*Decision*):

| Wert | Bedeutung |
|---|---|
| **Sticky – bevorzugtes Klingeln** (`sticky_first`) | Treffer: Die zugeordnete Nebenstelle klingelt zuerst. |
| **Standard-Routing** (`default`) | Kein Treffer / pausiert / Fehler → normaler Weg über die Warteschlange. |
| **Zuordnung angelegt/aktualisiert** (`created`) | Ein ausgehender Anruf hat eine Zuordnung erzeugt oder erneuert. |
| **Ignoriert (anonym/ungültig)** (`ignored`) | Anruf ohne verwertbare Nummer oder ohne qualifizierendes Ereignis. |
| **Presence aktualisiert** (`updated`) | Presence-/Registrierungsstatus einer Nebenstelle wurde gesetzt. |
| **Fehler** (`error`) | Interner Fehler – der Anruf lief dennoch auf Standard-Routing. |

**Mögliche Fallback-Gründe** (*Fallback Reason*) bei `default`:

| Wert | Bedeutung |
|---|---|
| **Keine gültige Zuordnung** (`no_match`) | Zur Nummer existiert keine gültige Zuordnung (oder Nummer anonym). |
| **Zuordnung abgelaufen** (`expired`) | Die Gültigkeitsdauer war überschritten. |
| **Nebenstelle nicht verfügbar** (`unavailable`) | Die zugeordnete Nebenstelle war laut Presence besetzt/DND/offline und wurde übersprungen. |
| **Sticky pausiert (Not-Aus)** (`sticky_disabled`) | Der Not-Aus (Abschnitt 4) war aktiv. |

**Nützliche Filter:** **Eingehend** (*Inbound*), **Ausgehend** (*Outbound*),
**Sticky-Treffer** (*Sticky hits*), **Fehler** (*Errors*) sowie Gruppieren nach
**Ereignis** (*Event*) oder **Entscheidung** (*Decision*).

### 5.3 Nebenstellen (optional)

**Callback Routing → Konfiguration → Nebenstellen** (*Callback Routing →
Configuration → Extensions*) listet die bekannten 3CX-Nebenstellen mit ihrem
Presence-Status. Diese Ansicht ist **für die Grundfunktion nicht erforderlich** –
die Nebenstelle des Kollegen ist ohnehin Teil der automatisch erzeugten
Zuordnung. Sie ist nur nützlich, um (a) einer Nebenstelle einen **Mitarbeiter**
(*Employee*) zur besseren Lesbarkeit zuzuordnen oder (b) die Überspringen-Regeln
(Besetzt/DND/Offline) zu nutzen – Letzteres setzt voraus, dass 3CX
Presence-Meldungen an Odoo schickt.

---

## 6. Die 3CX-Seite (kompakt)

Die vollständige Anleitung inklusive Beispiel-Deployment steht in
[`../docs/3cx_cfd/README.md`](../docs/3cx_cfd/README.md) und
[`../docs/CONFIG_GUIDE.md`](../docs/CONFIG_GUIDE.md). Kurzüberblick:

- **Eingehend (Routing, Pflicht):** Das Anrufskript `SmartCallbackRouting.cs` wird
  in der 3CX-Adminkonsole eingefügt und auf den Trigger **„Wenn ein Anruf auf
  einem Trunk eingeht"** (*When a call is received on a trunk*) gelegt – **nicht**
  auf einen DID- oder Wahlcode-Trigger. Im Skriptkopf werden `OdooBaseUrl`, der
  `ApiKey` (der API-Schlüssel aus Abschnitt 3) und ein kurzer `HttpTimeoutMs`
  (z. B. 1200) gesetzt. Der Filter `OnlyDidSuffix` begrenzt das Skript auf Ihre
  Hauptnummer.
- **Ausgehend (Erfassung, Pflicht):** Im Produktivbetrieb erfasst das gemeinsame
  **3CX-CRM-Template** (`3cx_odoo_v20.xml`) die ausgehenden Anrufe über das
  **Call Journaling** und meldet sie an Odoo (`/api/3cx/outbound`). Dazu wird im
  CRM-Integrationsdialog der Parameter **„Smart Callback API Key"** mit dem
  Odoo-API-Schlüssel gefüllt und das **Call Journaling aktiviert**. Ohne diese
  Erfassung entstehen keine Zuordnungen. (Dieser Parameter ist ein anderer als der
  Kontakt-Such-Schlüssel des `3cxcrm`-Teils.)
- **Nebenstellen-Weiterleitung (ersetzt Erst-Klingeln/Fallback):** Timeout und
  Fallback erzwingt **nicht** Odoo, sondern die Weiterleitungsregeln der
  3CX-Nebenstelle. Stellen Sie die zugeordneten Nebenstellen so ein, dass
  **„Keine Antwort"** (*Unanswered calls*) **und** **„Besetzt oder nicht
  registriert"** (*Busy or not registered*) auf die System-Nebenstelle der
  Warteschlange gehen – mit **abgeschalteter Mailbox** (Voicemail-Häkchen aus).
  So klingelt zuerst der Kollege und danach wieder die Warteschlange, statt in der
  Mailbox zu landen.

> **Wichtig:** Das 3CX-Skript braucht einen **eigenen Fallback**, falls Odoo
> gänzlich nicht erreichbar ist. Die Odoo-API antwortet zwar nie blockierend, kann
> aber bei komplettem Ausfall gar nicht antworten – dann muss die Zeitüberschreitung
> in 3CX den Anruf regulär in die Warteschlange leiten.

---

## 7. Fehlersuche

| Symptom | Zu prüfen |
|---|---|
| **Kein Sticky – es kommt immer „Standard-Routing"** | Ist der **Not-Aus** (Abschnitt 4) versehentlich aktiv? · Stimmt der **API-Schlüssel** in Odoo mit dem in 3CX (Skript `ApiKey` und CRM-Parameter) überein? · Ist die **Zuordnung abgelaufen** (Filter „Gültig" prüfen, ggf. TTL erhöhen)? · Passt der Filter **`OnlyDidSuffix`** im Skript zu Ihrer Hauptnummer? |
| **Skript-Log zeigt kein „TRIGGER fired"** | Der Trigger bzw. der ausgewählte **Trunk** ist falsch. Das Inbound-Skript muss auf **„Wenn ein Anruf auf einem Trunk eingeht"** liegen, nicht auf dem Wahlcode-Trigger. |
| **Der Anrufer wird aufgelegt** | Das Skript liegt auf dem **DID-Trigger** statt auf dem **Trunk-Trigger**: Beim DID-Trigger bedeutet `return false` „auflegen". Auf den Trunk-Trigger umstellen – dort heißt `return false` „normal weiterleiten". |
| **Zuordnungen entstehen gar nicht** | Läuft der ausgehende Anruf tatsächlich **über 3CX** (Tischtelefon/Softphone/App) und nicht über ein privates Handy? · Ist das **Call Journaling** im CRM-Template aktiviert und der `Smart Callback API Key` gesetzt? |
| **Erwarteter Kollege klingelt nicht, obwohl Zuordnung gültig** | Wird **Presence** gemeldet und greift eine **Überspringen-Regel** (Besetzt/DND/Offline)? Im Routing-Protokoll erscheint dann der Fallback-Grund **Nebenstelle nicht verfügbar**. |

> Erste Anlaufstelle ist immer das **Routing-Protokoll** (Abschnitt 5.2): Die
> Spalten **Entscheidung** und **Fallback-Grund** sagen Ihnen genau, warum ein
> Anruf so geleitet wurde.

---

## 8. Datenschutz

- Odoo speichert ausschließlich **normalisierte Telefonnummern** als temporäre
  Zuordnung zur Nebenstelle – mit einer festen **Gültigkeitsdauer (TTL)**.
- Ein **Cron-Job** löscht abgelaufene Zuordnungen **automatisch alle 30 Minuten**
  (in Odoo: *Einstellungen → Technisch → Geplante Aktionen →* „Smart Callback
  Routing: Clean up expired mappings"). Es sammeln sich also keine dauerhaften
  Rufnummern-Historien an.
- Die Protokollierung der Routing-Entscheidungen lässt sich in den Einstellungen
  (Block **Protokollierung**) abschalten, falls gewünscht.
- Es entsteht **keine dauerhafte CRM-Zuordnung** eines Kontakts zu einem
  Mitarbeiter – die Affinität ist bewusst kurzlebig.

---

*Stand: Modulversion 19.0.2.0.0. Screenshots der genannten Masken sind noch offen
(TODO) und können bei einer späteren Überarbeitung aus der laufenden Instanz
ergänzt werden.*
