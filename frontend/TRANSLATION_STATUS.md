# Translation status — English / ಕನ್ನಡ

Kannada is **deliberately partial**. Any key absent from `messages/kn.json` renders in
English at runtime, because `LocaleProvider` deep-merges English underneath Kannada.

The reason is stated plainly: **wrong Kannada in a government-facing product is a worse
outcome than a correct English fallback.** Short, high-frequency terms were translated
where confidence is high. Longer descriptive prose was left for a qualified translator
rather than guessed.

Nothing below is broken. Everything renders; the untranslated items simply render in
English.

---

## ✅ Translated (high confidence)

Short nouns, navigation labels and button text — the vocabulary a duty officer reads
dozens of times a shift.

| Area | Keys |
|---|---|
| Brand | `brand.org` — ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ |
| Navigation | all 9 sidebar items + `adminUsers` |
| Common | `logout`, `officer`, `investigator`, `search`, `district`, `status`, `date`, `close`, `cancel`, `save`, `download` |
| Auth | `username`, `accessKey`, `authorize`, `twoFactor`, `authCode`, `verify`, `verifying` |
| Topbar | `alertFeed`, `language` |
| Dashboard | `title`, `totalFirs`, `activeInvestigations`, `topDistricts`, `topStations` |
| Public safety | `title`, `emergency`, `cyberFraud`, `safetyLevel`, `findDistrict`, all three bands, all three trends |

---

## ⏳ Awaiting a qualified Kannada translator

These keys exist in `en.json`, are **absent** from `kn.json`, and therefore fall back to
English. Grouped by why they were held back.

### Longer descriptive sentences
Full sentences where register and phrasing matter more than vocabulary, and a literal
translation would read badly.

- `auth.securedEndpoint`, `auth.twoFactorPrompt`, `auth.mfaScanHint`
- `auth.errorBothFields`, `auth.errorAuthFailed`, `auth.errorSixDigits`,
  `auth.errorInvalidCode`, `auth.errorUnreachable`
- `common.loading`, `common.noCommands`, `common.typeCommand`
- `topbar.noAlerts`, `topbar.dismissAll`, `topbar.switchToLight`, `topbar.switchToDark`
- `publicSafety.noMatch`, `publicSafety.unavailable`, `publicSafety.loadingMap`
- All 9 `nav.*Desc` hover descriptions

### Terms where I was not confident of the accepted KSP usage
Police and legal vocabulary often has a settled departmental form that differs from a
dictionary rendering. These need someone who knows the in-service term.

| Key | English | Note |
|---|---|---|
| `brand.console` | Karnataka Police Command Console | "Command console" — transliterate or translate? |
| `topbar.gatewayOnline` | Catalyst Online | Product/system name; may be left as-is |
| `topbar.searchPlaceholder` | Search 1.68M FIR cases… | Number formatting differs in Kannada convention |
| `dashboard.solveRate` | Crime Solve Rate | Is the departmental term disposal / detection / conviction rate? |
| `dashboard.monthlyTrend` | Crime Frequency — Monthly Trend | |
| `dashboard.anomalyFeed` | Statistical Anomaly Alert Feed | |
| `dashboard.forecastEngine` | AI Forecast Engine | |
| `common.navigation` | Navigation | ಸಂಚರಣೆ vs the transliteration — unsure which reads better in-product |

### Strings that come from the backend, not the message files
These are served by the API and are **not** translatable through `kn.json` at all. If
they need Kannada, the backend must return a localised variant — say the word and I will
add a locale parameter to the public endpoint.

- `publicSafety` disclaimer text
- `publicSafety` methodology text
- All district safety tips
- District names (currently English transliterations in the source data)

---

## How to add a translation

1. Add the key to `messages/kn.json`, matching the nesting in `messages/en.json`.
2. Nothing else. The deep merge picks it up; no code change, no rebuild step.
3. Remove the entry from the pending list above.

To check coverage at any time:

```bash
node -e "const en=require('./messages/en.json'),kn=require('./messages/kn.json');const f=(o,p='')=>Object.entries(o).flatMap(([k,v])=>k.startsWith('_')?[]:typeof v==='object'?f(v,p+k+'.'):[p+k]);const E=f(en),K=new Set(f(kn));console.log(`${K.size}/${E.length} keys translated`);console.log('missing:',E.filter(k=>!K.has(k)).join(', '))"
```
