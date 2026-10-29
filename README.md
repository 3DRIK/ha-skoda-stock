# Škoda Stock (Home Assistant / HACS)

Sleduje skladové a predvádzacie autá Škoda na skoda-auto.sk (predvolene Elroq a Epiq). Raz za 3 hodiny stiahne
všetky stránky ponuky, uloží históriu cien a pošle udalosti pri novej ponuke, znížení ceny, rezervácii alebo zmiznutí auta.

## Inštalácia
1. Nahraj repozitár na GitHub (v `manifest.json` nahraď `CHANGE_ME`). HACS → ⋮ → *Custom repositories* → typ *Integration*.
2. Nainštaluj *Škoda Stock*, reštartuj HA.
3. Nastavenia → Zariadenia a služby → Pridať integráciu → *Škoda Stock*.
4. Do dashboardu pridaj kartu `type: custom:skoda-stock-card` (zdroj sa registruje automaticky, netreba pridávať resource).
   Voliteľne `title:` a `page_size:`.

## Nastavenia (aj neskôr cez ⚙)
- **Modely**: kódy (BIBQ Elroq, BIBT Epiq; ďalšie sa dajú pridať ručne).
- **Interval**: predvolene 3 h.
- **Limit ceny / nájazdu, predvádzacie**: týka sa iba upozornení. Obľúbené autá upozorňujú vždy.
- **Šablóna odkazu**: pozri nižšie.

## Odkaz na auto
Presnú adresu detailu auta na skoda-auto.sk som nemohol overiť. Predvolený odkaz vedie na zoznam Škody
filtrovaný na model. Nájdi si na webe detail ľubovoľného auta, skopíruj jeho URL a v nastaveniach nahraď časť
identifikátora zástupným symbolom: `{key}`, `{id}`, `{vin}`, `{commission}` alebo `{model_code}`.
Príklad: `https://www.skoda-auto.sk/.../detail/{key}`. Odkaz na web predajcu je v dátach vždy (`dealer_website`).

## Výbava a balíky
Pri každom novom aute sa raz načíta detail (`getCarDetail?id=...`) a uloží sa výbava, balíky a pár technických
údajov (čistá kapacita batérie, DC nabíjanie, zrýchlenie, batožinový priestor). Pri novej ponuke sa detail načíta ešte
pred upozornením, takže správa obsahuje názvy balíkov. Ostatné autá sa doťahujú na pozadí po jednom s pauzou 1,5 s
(prvé načítanie ~200 áut trvá zhruba 5 minút). Neúspešný pokus sa opakuje najskôr o 6 hodín alebo službou
`skoda_stock.fetch_equipment`.

V karte je panel *Výbava a balíky*: zaškrtni balíky alebo jednotlivé položky, vyhľadávať sa dá v texte
(napr. „tepelné čerpadlo"). Režim *Musí mať všetko* / *Stačí aspoň jedno* sa objaví pri viac ako jednom výbere.
Autá, ktorým výbava ešte nebola načítaná, sa pri aktívnom filtri výbavy skryjú (karta to napíše pri počte áut).
Balíky sa berú zo skupiny `packages` v odpovedi, ostatná výbava zo zvyšných skupín.

## Entity
Počet áut, Najlacnejšie auto, Nové ponuky za 24 h, Zníženia cien za 24 h, Rezervované autá, Predvádzacie autá,
Obľúbené autá, Posledná aktualizácia a binárny senzor *Zmena u obľúbených* (cena / rezervácia / zmiznutie za 24 h).

## Udalosti (`event_data` má `title`, `message`, `url`, `image`, `vin`, `price`, ...)
`skoda_stock_new_car`, `skoda_stock_price_drop` (`old_price`, `new_price`, `diff`), `skoda_stock_price_increase`,
`skoda_stock_reserved`, `skoda_stock_unreserved`, `skoda_stock_car_removed` (`was_reserved`).

Prvé načítanie nič neoznamuje (všetko sa berie ako východiskový stav). Auto sa považuje za preč, až keď chýba
v dvoch po sebe idúcich kompletných načítaniach.

## Upozornenia
Skopíruj `blueprints/automation/skoda_stock/notify.yaml` do `/config/blueprints/automation/skoda_stock/` a vytvor
automatizáciu z blueprintu (zadaj napr. `notify.mobile_app_telefon`). Pre inú službu než mobilnú appku odstráň
v blueprinte položky `url`, `clickAction` a `image`.

## Služby
`skoda_stock.refresh` (najviac raz za 10 min), `skoda_stock.add_favorite` / `remove_favorite` (`vin`).
Obľúbené sa dajú prepínať aj hviezdičkou v karte.
