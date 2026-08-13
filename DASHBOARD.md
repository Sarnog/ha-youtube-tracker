🇳🇱 [Nederlands](#op-je-dashboard) | 🇬🇧 [English](#on-your-dashboard)

---

# Op je dashboard

De sensor bevat alles wat je nodig hebt om je ongeziene video's te tonen. Dit
bestand geeft drie uitgewerkte varianten, van eenvoudig naar fraai.

**Vervang overal `sensor.youtube_kanaalnaam` door je eigen sensor.** Je vindt
de juiste naam onder **Ontwikkelhulpmiddelen → Statussen**, door op `youtube`
te zoeken. Vergeet je dat, dan krijg je `TypeError: 'NoneType' object is not
iterable` — dat is Home Assistant die zegt "die entiteit bestaat niet".

## Wat er in de sensor zit

| Veld | Inhoud |
| --- | --- |
| `state` | Aantal ongeziene video's |
| `kanaal` | Naam van het kanaal |
| `channel_id` | Het YouTube channel-ID |
| `peildatum` | Vanaf wanneer video's meetellen |
| `videos` | De lijst hieronder, maximaal 50 lang |
| `nieuwste_titel` / `nieuwste_url` | Snelkoppeling naar de bovenste video |

Elke video in `videos` heeft: `video_id`, `titel`, `url`, `thumbnail`,
`gepubliceerd`, `kijk_url` en `markeer_url`.

Het verschil tussen die laatste twee:

| Link | Wat er gebeurt |
| --- | --- |
| `kijk_url` | Vinkt de video af **en** opent hem op YouTube |
| `markeer_url` | Vinkt alleen af; je blijft waar je bent |

---

## Variant 1: markdown, werkt altijd

Geen custom cards nodig. Thumbnails zijn klikbaar, met een aparte
afvink-link eronder.

```yaml
type: markdown
content: |-
  {% set videos = state_attr('sensor.youtube_kanaalnaam', 'videos') or [] %}
  {% set maanden = ['januari','februari','maart','april','mei','juni',
     'juli','augustus','september','oktober','november','december'] %}
  {% if videos | count == 0 %}
  ### Alles bekeken

  Er staat niets meer open op dit kanaal.
  {% else %}
  ### {{ state_attr('sensor.youtube_kanaalnaam', 'kanaal') }} — {{ videos | count }} ongezien

  {% for v in videos %}
  {% set d = v.gepubliceerd | as_datetime | as_local %}
  [![]({{ v.thumbnail }})]({{ v.kijk_url }})

  **[{{ v.titel }}]({{ v.kijk_url }})**
  {{ d.day }} {{ maanden[d.month - 1] }} · [afvinken]({{ v.markeer_url }})

  {% endfor %}
  {% endif %}
```

De `or []` achter `state_attr` is belangrijk: die vangt het geval af dat de
sensor nog niet bestaat of nog geen gegevens heeft.

---

## Variant 2: tegels met knoppen (aanbevolen)

Vereist twee custom cards uit HACS: **config-template-card** en
**button-card**.

Dit geeft een raster van tegels met de thumbnail als achtergrond en de titel
eroverheen. **Tikken** opent de video en vinkt hem af, **lang indrukken**
vinkt alleen af. Bovenaan staat een knop om alles in één keer af te vinken.

**De sensornaam staat maar op één plek**, helemaal bovenin bij `SENSOR`. De
rest van de kaart leest hem daar uit, ook de `entities`-lijst.

```yaml
type: custom:config-template-card
variables:
  # De enige plek waar je je eigen sensor invult. Let op de dubbele
  # aanhalingstekens: de buitenste zijn voor YAML, de binnenste maken er
  # een tekstwaarde van voor de kaart.
  SENSOR: "'sensor.youtube_kanaalnaam'"
entities:
  - ${SENSOR}
card:
  type: vertical-stack
  cards: >-
    ${[
      {
        type: 'horizontal-stack',
        cards: [
          {
            type: 'custom:button-card',
            entity: SENSOR,
            name: states[SENSOR].attributes.kanaal,
            icon: 'mdi:youtube',
            show_state: true,
            state_display: states[SENSOR].state + ' ongezien',
            styles: {
              card: [{height: '110px'}],
              icon: [{color: '#FF0000'}, {width: '40px'}],
              name: [{'font-weight': '600'}]
            }
          },
          {
            type: 'custom:button-card',
            name: 'Alles afvinken',
            icon: 'mdi:check-all',
            tap_action: {
              action: 'perform-action',
              perform_action: 'youtube_tracker.mark_all_watched',
              data: { entity_id: SENSOR }
            },
            confirmation: { text: 'Alles van dit kanaal afvinken?' },
            styles: {
              card: [{height: '110px'}],
              icon: [{width: '40px'}],
              name: [{'font-weight': '600'}]
            }
          }
        ]
      }
    ].concat(
      (states[SENSOR].attributes.videos || []).length === 0
        ? [{ type: 'markdown', content: 'Je bent bij, er staat niets meer open.' }]
        : (states[SENSOR].attributes.videos || []).map(v => ({
            type: 'custom:button-card',
            tap_action: { action: 'url', url_path: v.kijk_url },
            hold_action: {
              action: 'perform-action',
              perform_action: 'youtube_tracker.mark_watched',
              data: { video_id: v.video_id }
            },
            show_icon: false,
            show_name: true,
            show_label: true,
            name: v.titel,
            label: new Date(v.gepubliceerd).toLocaleDateString('nl-NL',
                     { day: 'numeric', month: 'long' }),
            styles: {
              card: [
                {'background-image':
                  'linear-gradient(to top, rgba(0,0,0,.92) 0%,' +
                  ' rgba(0,0,0,.45) 45%, rgba(0,0,0,.05) 100%), url("' +
                  v.thumbnail + '")'},
                {'background-size': 'cover'},
                {'background-position': 'center'},
                {height: '160px'},
                {padding: '12px'},
                {'justify-content': 'flex-end'},
                {'align-items': 'flex-start'},
                {'border-radius': '12px'}
              ],
              grid: [
                {'grid-template-areas': '"n" "l"'},
                {'grid-template-rows': 'min-content min-content'}
              ],
              name: [
                {color: 'white'},
                {'font-size': '15px'},
                {'font-weight': '600'},
                {'text-align': 'left'},
                {'line-height': '1.3'},
                {'text-shadow': '0 1px 4px rgba(0,0,0,.9)'},
                {display: '-webkit-box'},
                {'-webkit-line-clamp': '2'},
                {'-webkit-box-orient': 'vertical'},
                {overflow: 'hidden'}
              ],
              label: [
                {color: 'rgba(255,255,255,.85)'},
                {'font-size': '12px'},
                {'text-align': 'left'},
                {'text-shadow': '0 1px 4px rgba(0,0,0,.9)'}
              ]
            }
          }))
    )}
```

Let op: de blokken tussen `${ }` zijn JavaScript, geen Jinja. Daarom
`states[SENSOR].attributes.videos` in plaats van `state_attr(...)`, en `||`
in plaats van `or`.

De twee tegels bovenaan krijgen allebei `height: '110px'`, anders wordt de
linker hoger doordat die een extra regel met de teller heeft.

### Meerdere kanalen zonder knippen en plakken

Heb je meer kanalen, dan wil je de kaart niet per kanaal kopiëren. Met
**decluttering-card** maak je er één sjabloon van. Zet dit bovenin je
dashboard via de rauwe configuratie-editor (drie puntjes → **Rauwe
configuratie-editor bewerken**):

```yaml
decluttering_templates:
  youtube_kanaal:
    card:
      type: custom:config-template-card
      variables:
        SENSOR: "'[[sensor]]'"
      entities:
        - ${SENSOR}
      card:
        # ... hier de rest van de kaart hierboven, ongewijzigd ...
```

Daarna is een kanaal toevoegen nog maar drie regels:

```yaml
type: custom:decluttering-card
template: youtube_kanaal
variables:
  - sensor: sensor.youtube_kanaalnaam
```

---

## Variant 3: compact, alleen de nieuwste

Voor op een druk dashboard, waar je alleen wilt zien of er iets nieuws is.
Geen custom cards nodig.

```yaml
type: conditional
conditions:
  - condition: numeric_state
    entity: sensor.youtube_kanaalnaam
    above: 0
card:
  type: markdown
  content: |-
    {% set s = 'sensor.youtube_kanaalnaam' %}
    **{{ state_attr(s, 'kanaal') }}** — {{ states(s) }} ongezien

    [{{ state_attr(s, 'nieuwste_titel') }}]({{ (state_attr(s, 'videos') or [{}])[0].get('kijk_url', '#') }})
```

De `conditional`-kaart verbergt het geheel zodra je alles hebt bekeken.

---

## Meerdere kanalen onder elkaar

Heb je meerdere kanalen, herhaal dan de kaart per sensor. Wil je het
overzichtelijk houden, zet ze dan in een **expander-card** of gebruik een
`grid` met twee kolommen.

Een totaalteller over alle kanalen maak je met een template-sensor via
**Instellingen → Apparaten & diensten → Helpers**:

```jinja
{{ states.sensor
   | selectattr('attributes.channel_id', 'defined')
   | map(attribute='state') | map('int', 0) | sum }}
```

---

## Werkt een link niet?

De klik-links wijzen naar `/api/youtube_tracker/...` op je eigen Home
Assistant. Ze werken zonder in te loggen, want ze dragen een handtekening die
alleen voor die ene video geldt.

Opent je dashboard de link niet, probeer dan variant 2: die gebruikt
`tap_action` in plaats van een markdown-link, en dat is een ander mechanisme
in de frontend.


---



# On your dashboard

The sensor holds everything you need to show your unwatched videos. This file
gives three worked-out variants, from simple to fancy.

**Replace `sensor.youtube_kanaalnaam` with your own sensor everywhere.** You
can find the right name under **Developer tools → States** by searching for
`youtube`. Forget it and you get `TypeError: 'NoneType' object is not
iterable` — that is Home Assistant telling you the entity does not exist.

## What the sensor holds

| Field | Contents |
| --- | --- |
| `state` | Number of unwatched videos |
| `kanaal` | Name of the channel |
| `channel_id` | The YouTube channel ID |
| `peildatum` | The cut-off date from which videos count |
| `videos` | The list below, 50 entries at most |
| `nieuwste_titel` / `nieuwste_url` | Shortcut to the top video |

Every video in `videos` has: `video_id`, `titel`, `url`, `thumbnail`,
`gepubliceerd`, `kijk_url` and `markeer_url`.

The difference between those last two:

| Link | What happens |
| --- | --- |
| `kijk_url` | Clears the video **and** opens it on YouTube |
| `markeer_url` | Only clears it; you stay where you are |

---

## Variant 1: markdown, always works

No custom cards needed. Thumbnails are clickable, with a separate clear link
underneath.

```yaml
type: markdown
content: |-
  {% set videos = state_attr('sensor.youtube_kanaalnaam', 'videos') or [] %}
  {% set months = ['January','February','March','April','May','June',
     'July','August','September','October','November','December'] %}
  {% if videos | count == 0 %}
  ### All caught up

  Nothing left on this channel.
  {% else %}
  ### {{ state_attr('sensor.youtube_kanaalnaam', 'kanaal') }} — {{ videos | count }} unwatched

  {% for v in videos %}
  {% set d = v.gepubliceerd | as_datetime | as_local %}
  [![]({{ v.thumbnail }})]({{ v.kijk_url }})

  **[{{ v.titel }}]({{ v.kijk_url }})**
  {{ d.day }} {{ months[d.month - 1] }} · [clear]({{ v.markeer_url }})

  {% endfor %}
  {% endif %}
```

The `or []` after `state_attr` matters: it covers the case where the sensor
does not exist yet or has no data.

---

## Variant 2: tiles with buttons (recommended)

Needs two custom cards from HACS: **config-template-card** and
**button-card**.

This gives a grid of tiles with the thumbnail as background and the title on
top. **Tapping** opens the video and clears it, **holding** only clears it. At
the top sits a button to clear everything at once.

Use the YAML from the Dutch section above — only the two label strings differ:
change `'nl-NL'` to your own locale and `'Alles afvinken'` to
`'Clear everything'`.

**The sensor name appears only once**, at the top under `SENSOR`. The rest of
the card reads it from there, including the `entities` list. Both top tiles get
`height: '110px'`, otherwise the left one grows taller because it carries an
extra line with the counter.

---

## Variant 3: compact, newest only

For a busy dashboard, where you only want to see whether something is new. No
custom cards needed.

```yaml
type: conditional
conditions:
  - condition: numeric_state
    entity: sensor.youtube_kanaalnaam
    above: 0
card:
  type: markdown
  content: |-
    {% set s = 'sensor.youtube_kanaalnaam' %}
    **{{ state_attr(s, 'kanaal') }}** — {{ states(s) }} unwatched

    [{{ state_attr(s, 'nieuwste_titel') }}]({{ (state_attr(s, 'videos') or [{}])[0].get('kijk_url', '#') }})
```

The `conditional` card hides the whole thing once you are caught up.

---

## Multiple channels

With several channels you do not want to copy the card per channel. Turn it
into a template with **decluttering-card**, through the raw configuration
editor (three dots → **Edit in raw configuration editor**):

```yaml
decluttering_templates:
  youtube_kanaal:
    card:
      type: custom:config-template-card
      variables:
        SENSOR: "'[[sensor]]'"
      entities:
        - ${SENSOR}
      card:
        # ... the rest of the card above, unchanged ...
```

After that, adding a channel is three lines:

```yaml
type: custom:decluttering-card
template: youtube_kanaal
variables:
  - sensor: sensor.youtube_channelname
```

A combined counter across all channels is a template sensor, created through
**Settings → Devices & services → Helpers**:

```jinja
{{ states.sensor
   | selectattr('attributes.channel_id', 'defined')
   | map(attribute='state') | map('int', 0) | sum }}
```

---

## A link does not work?

The click links point at `/api/youtube_tracker/...` on your own Home
Assistant. They work without signing in, because they carry a signature valid
for that one video only.

If your dashboard refuses to open the link, try variant 2: it uses
`tap_action` instead of a markdown link, which is a different mechanism in the
frontend.
