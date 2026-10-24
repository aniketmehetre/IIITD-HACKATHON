# Synthetic Scam Funnels — Public Deployment Guide

TinyFish autonomous browser agents execute inside remote cloud containers and **cannot access `localhost` or local IPs**. To run live detonation tests against these funnels, each variant should be deployed to a distinct public URL.

---

## Funnel Variants

1. **Variant A1** (`fixtures/funnels/variant_a1/`):
   - Type: Fake Lucky Draw / Voucher Lure (Orange theme)
   - Payee: `rewards.payout@stingtest` (₹49)
2. **Variant A2** (`fixtures/funnels/variant_a2/`):
   - Type: Fake Monsoon Cashback (Blue theme, same template family)
   - Payee: `rewards.payout@stingtest` (₹29)
3. **Variant B1** (`fixtures/funnels/variant_b1/`):
   - Type: Fake 5G Telecom Recharge (Dark theme, separate campaign)
   - Payee: `fastrecharge.cashier@stingtest` (₹19)
4. **Variant C1** (`fixtures/funnels/variant_c1/`):
   - Type: Benign Help Center Documentation (No forms, no payment)

---

## 5-Minute Free Deployment Options

### Option 1: Vercel (CLI or Web UI)
```bash
# Navigate to the variant folder and deploy
cd fixtures/funnels/variant_a1
npx vercel --yes --prod
```
Repeat for `variant_a2`, `variant_b1`, and `variant_c1`.

### Option 2: Netlify Drop / CLI
```bash
cd fixtures/funnels/variant_a1
npx netlify-cli deploy --prod --dir=.
```
Or drag-and-drop each directory directly into [app.netlify.com/drop](https://app.netlify.com/drop).

### Option 3: Cloudflare Pages
- Connect GitHub repo or run `npx wrangler pages deploy fixtures/funnels/variant_a1 --project-name=sting-funnel-a1`.

---

## Registering Public URLs

Once deployed, add your public URLs into `fixtures/funnel_urls.json`:

```json
{
  "variant_a1": "https://sting-funnel-a1.vercel.app",
  "variant_a2": "https://sting-funnel-a2.vercel.app",
  "variant_b1": "https://sting-funnel-b1.vercel.app",
  "variant_c1": "https://sting-funnel-c1.vercel.app"
}
```

---

## Safety & Legal Compliance Notice

All synthetic funnels strictly comply with security research guidelines:
- **Zero Real Brands:** All pages use fictitious names like *ExampleMart* and *QuickRecharge*.
- **Safe Fake UPI Suffix:** Every payee ends in `@stingtest`. Never use real bank PSP handles on public test pages.
- **Search Engine Blocking:** Every HTML file includes `<meta name="robots" content="noindex, nofollow">`.
- **Visible Disclaimer:** Every page carries the mandatory footer: `Synthetic STING test funnel - not a real service. Do not pay.`
- **No Data Collection:** Forms do not transmit or store submitted credentials anywhere.
