# ISI — Design System Specification
**Projet :** Institut de Sécurité Industrielle — Système de gestion interne  
**Version :** 1.0 — Février 2026  
**Usage :** Référence canonique pour la génération de tous les templates Django restants

---

## 1. Stack & dépendances externes

| Ressource | Version | CDN |
|---|---|---|
| Bootstrap CSS | 5.3.3 | `https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css` |
| Bootstrap JS Bundle | 5.3.3 | `https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js` |
| Bootstrap Icons | 1.11.3 | `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css` |
| Chart.js | 4.4.3 | `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js` |
| Google Fonts | — | Barlow Condensed (400/500/600/700) + Barlow (300/400/500/600) |

> **Règle absolue :** aucune autre librairie CSS ou JS ne doit être ajoutée. Tout le styling personnalisé est inline dans `<style>` dans `base.html` ou, pour la page de login, dans la page elle-même.

---

## 2. Typographie

### Familles
| Variable CSS | Famille | Usages |
|---|---|---|
| `--font-head` | `'Barlow Condensed', sans-serif` | Titres de page (`h1`), en-têtes de cartes (`h2`, `h3`), en-têtes de tableaux (`th`), `stat-value`, labels de formulaire sections, badges de navigation |
| `--font-body` | `'Barlow', sans-serif` | Tout le reste : corps de texte, inputs, boutons, paragraphes |

### Échelle typographique
| Élément | Famille | Taille | Poids | Particularités |
|---|---|---|---|---|
| `h1` page header | Condensed | 26px | 700 | `letter-spacing: .3px` |
| Topbar title | Condensed | 20px | 700 | `letter-spacing: .3px` |
| Card header `h3` | Condensed | 17px | 700 | `letter-spacing: .3px` |
| `stat-value` | Condensed | 24px | 700 | `line-height: 1` |
| `stat-label` | Body | 12px | 600 | `uppercase, letter-spacing: .7px` |
| Nav item links | Body | 13.5px | 500 | — |
| Sous-nav items | Body | 13px | 500 | — |
| `form-label` | Body | 12px | 600 | `uppercase, letter-spacing: .5px` |
| `form-section-title` | Condensed | 13px | 700 | `uppercase, letter-spacing: 1px`, bordure-bas amber 2px |
| Table `th` | Condensed | 11px | 700 | `uppercase, letter-spacing: 1.2px` |
| Table `td` | Body | 14.5px | 400 | — |
| Body base | Body | 14.5px | 400 | `line-height: 1.6` |
| Badges `.isi-badge` | Body | 11px | 600 | `letter-spacing: .3px` |
| Nav labels sidebar | Body | 10px | 600 | `uppercase, letter-spacing: 1.5px` |
| Sidebar brand | Condensed | 16px | 700 | `uppercase, letter-spacing: .5px` |
| Login `h1` (standalone) | Condensed | 42px | 800 | `uppercase, letter-spacing: 1px` |

---

## 3. Palette de couleurs — Design Tokens CSS

```css
:root {
  /* Sidebar */
  --sidebar-w: 260px;
  --sidebar-bg: #0f172a;          /* Slate 900 — fond sidebar */
  --sidebar-border: rgba(255,255,255,.06);
  --sidebar-text: #94a3b8;         /* Slate 400 — texte inactif */
  --sidebar-active: #f59e0b;       /* Amber 500 — item actif */
  --sidebar-active-bg: rgba(245,158,11,.10);

  /* Accent (brand) */
  --accent: #f59e0b;               /* Amber 500 — couleur principale */
  --accent-dark: #d97706;          /* Amber 600 — hover */
  --accent-soft: rgba(245,158,11,.12); /* Fond doux accent */

  /* Statuts */
  --success: #10b981;              /* Emerald 500 */
  --danger: #ef4444;               /* Red 500 */

  /* Layout */
  --body-bg: #f8fafc;              /* Slate 50 — fond page */
  --card-bg: #ffffff;
  --card-border: #e2e8f0;          /* Slate 200 */
  --text-primary: #0f172a;         /* Slate 900 */
  --text-muted: #64748b;           /* Slate 500 */
  --header-h: 64px;

  /* Shape */
  --radius: 10px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,.10);
}
```

### Couleurs sémantiques (toutes les variantes)
| Nom | Hex / rgba | Utilisation |
|---|---|---|
| Amber 500 | `#f59e0b` | Accent principal, bouton primaire, actif sidebar, badges "amber", focus ring |
| Amber 600 | `#d97706` | Hover sur amber |
| Amber soft | `rgba(245,158,11,.12)` | `card-icon.amber`, `isi-badge.amber`, avatar sidebar |
| Emerald 500 | `#10b981` | `--success`, `card-icon.green`, `isi-badge.green` |
| Emerald text | `#065f46` | Texte sur fond vert |
| Blue 500 | `#3b82f6` | `card-icon.blue`, `isi-badge.blue` |
| Blue text | `#1e40af` | Texte sur fond bleu |
| Red 500 | `#ef4444` | `--danger`, erreurs, `isi-badge.red` |
| Red text | `#991b1b` | Texte sur fond rouge |
| Purple 500 | `#8b5cf6` | `card-icon.purple` (graphiques, rapports) |
| Slate 900 | `#0f172a` | Fond sidebar, `--text-primary`, texte sur fond amber |
| Slate 50 | `#f8fafc` | `--body-bg`, fond thead tableaux |
| Slate 200 | `#e2e8f0` | `--card-border`, séparateurs |
| Slate 400 | `#94a3b8` | `--sidebar-text`, placeholders, hints |
| Slate 500 | `#64748b` | `--text-muted`, labels, sous-titres |

### Focus ring
Toujours : `box-shadow: 0 0 0 3px rgba(245,158,11,.15)` (amber) pour inputs et checkboxes.

---

## 4. Layout

### Structure générale
```
body
├── #sidebar-overlay        (mobile uniquement)
├── nav#sidebar             (260px, fixed, left, full height)
│   ├── .sidebar-brand      (64px height, logo + texte ISI)
│   ├── .sidebar-section    (scrollable, flex:1)
│   │   ├── .nav-label      (section headers)
│   │   ├── .nav-item-link  (liens directs)
│   │   └── .nav-sub > .nav-item-link  (sous-nav collapsible)
│   └── .sidebar-footer     (utilisateur connecté)
└── #main-wrap              (margin-left: 260px)
    ├── header#topbar       (64px sticky, blanc, breadcrumb + actions)
    ├── div (flash messages, padding 12px 28px 0)
    └── main#page-content   (padding: 28px)
```

### Grille
- Bootstrap 12 colonnes.
- Gouttières standard : `g-3` (12px) pour les champs de formulaires, `g-4` (24px) pour les groupes de cartes.
- Mise en page courante : `col-lg-8` (formulaire principal) + `col-lg-4` (panneau latéral).
- Centrage formulaires standalone : `col-lg-5 col-md-7` avec `justify-content-center`.

### Breakpoints responsifs
- `≤ 991px` : sidebar masquée (`translateX(-100%)`), toggle visible, contenu `padding: 20px 16px`.
- `≤ 768px` (login uniquement) : panneau gauche masqué, formulaire pleine largeur.

---

## 5. Composants

### 5.1 Sidebar

```
nav#sidebar
  background: #0f172a | width: 260px | fixed | border-right: 1px solid rgba(255,255,255,.06)
```

**Brand :**  
- Icône 34×34px amber (border-radius: 8px), avec `bi-shield-fill-check`  
- Texte "ISI" Condensed 16px/700, sous-titre 10px slate-400

**Nav items :**
- Hauteur de ligne : padding `9px 20px`  
- Bordure gauche 3px transparent → amber quand actif  
- Fond actif : `rgba(245,158,11,.10)`  
- Couleur active : `#f59e0b`, inactive : `#94a3b8`

**Sous-navigation (collapse) :**
- `padding-left: 50px`
- Fond `rgba(0,0,0,.2)`
- Indicateur chevron via `::after` avec rotation à 180° si ouvert

**Badge count :** Bulle amber à droite du texte (`margin-left: auto`), 10px/700, border-radius: 20px.

**Footer utilisateur :**
- Avatar 34×34px circulaire, bordure amber 1.5px, initiale Condensed  
- Nom 13px/600 `#e2e8f0`, rôle 11px slate-400  
- Liens icônes à droite (profil + déconnexion)

---

### 5.2 Topbar

```
header#topbar
  height: 64px | background: #fff | border-bottom: 1px solid #e2e8f0
  padding: 0 28px | sticky top: 0 | z-index: 1030
```

- **Breadcrumb :** `bi-house-fill` (12px) → `bi-chevron-right` (10px) → `<span>` texte courant (500, primary)
- **Topbar actions :** `.topbar-btn` avec variante `.primary` (fond amber)

**`.topbar-btn`**
```css
border: 1px solid #e2e8f0 | border-radius: 8px | padding: 6px 12px
font-size: 13px | color: #64748b | gap: 6px
hover: border-color amber, color amber
```
**`.topbar-btn.primary`**
```css
background: #f59e0b | border-color: #f59e0b | color: #0f172a | font-weight: 600
hover: background #d97706
```

---

### 5.3 Cards — `.isi-card`

```css
background: #fff | border: 1px solid #e2e8f0 | border-radius: 10px
box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06)
```

**`.isi-card-header`**
```css
padding: 18px 24px 14px | border-bottom: 1px solid #e2e8f0
display: flex | align-items: center | gap: 12px
```
- Contient systématiquement un `.card-icon` + `<h3>` Condensed 17px/700

**`.card-icon`** (34×34px, border-radius: 8px)
| Variante | Fond | Couleur |
|---|---|---|
| `.amber` | `rgba(245,158,11,.12)` | `#f59e0b` |
| `.green` | `rgba(16,185,129,.12)` | `#10b981` |
| `.blue` | `rgba(59,130,246,.12)` | `#3b82f6` |
| `.red` | `rgba(239,68,68,.12)` | `#ef4444` |
| `.purple` | `rgba(139,92,246,.12)` | `#8b5cf6` |

**`.isi-card-body`** : `padding: 24px`

**KPI card** (stat card compacte) : `.isi-card-body` avec flex, gap 16px, `.card-icon` 44×44px/font-size 20px/border-radius 12px, `stat-value` + `stat-label`.

---

### 5.4 Tableaux — `.isi-table`

```css
width: 100% | border-collapse: collapse
```
- **`thead`** : `background: #f8fafc`, `border-bottom: 2px solid #e2e8f0`
- **`th`** : Condensed, 11px, 700, uppercase, `letter-spacing: 1.2px`, slate-500, `padding: 12px 16px`
- **`td`** : `padding: 13px 16px`, `border-bottom: 1px solid #e2e8f0`, vertical-align: middle
- **Hover row** : `background: #f8fafc`
- **Dernière ligne** : `border-bottom: none`
- Wrapper : `<div style="overflow-x:auto;">` autour du tableau

---

### 5.5 Badges — `.isi-badge`

```css
display: inline-flex | align-items: center | gap: 4px
font-size: 11px | font-weight: 600 | padding: 3px 10px
border-radius: 20px | letter-spacing: .3px
```

| Variante | Fond | Texte |
|---|---|---|
| `.amber` | `rgba(245,158,11,.12)` | `#92400e` |
| `.green` | `rgba(16,185,129,.12)` | `#065f46` |
| `.red` | `rgba(239,68,68,.12)` | `#991b1b` |
| `.blue` | `rgba(59,130,246,.12)` | `#1e40af` |
| `.gray` | `#f1f5f9` | `#475569` |

Usage systématique des icônes Bootstrap Icons dans les badges de statut et de rôle.

---

### 5.6 Boutons

| Classe | Fond | Bordure | Texte | Hover |
|---|---|---|---|---|
| `.btn-amber` | `#f59e0b` | `2px solid #f59e0b` | `#0f172a` | fond + bordure `#d97706` |
| `.btn-outline-amber` | transparent | `2px solid #f59e0b` | `#f59e0b` | fond `#f59e0b`, texte `#0f172a` |
| `.btn-ghost` | transparent | `2px solid #e2e8f0` | `#64748b` | bordure `#64748b`, texte `#0f172a` |
| `.btn-danger-soft` | `rgba(239,68,68,.1)` | `2px solid transparent` | `#ef4444` | fond `#ef4444`, texte `#fff` |
| `.btn-sm` | — | — | — | `padding: 5px 12px`, 12.5px |

Base commune `.btn` : `font-family: var(--font-body)`, 600, 13.5px, `border-radius: 8px`, `padding: 8px 18px`, `display: inline-flex; align-items: center; gap: 6px`.

---

### 5.7 Formulaires

**`.form-label`**
```css
font-size: 12px | font-weight: 600 | letter-spacing: .5px
text-transform: uppercase | color: #64748b | margin-bottom: 6px
```

**`.form-control` / `.form-select`**
```css
border-radius: 8px | border: 1px solid #e2e8f0
font-family: Barlow | font-size: 14px | padding: 9px 13px
color: #0f172a | background: #fff
focus: border-color #f59e0b, box-shadow 0 0 0 3px rgba(245,158,11,.15)
is-invalid: border-color #ef4444
```

**`.input-icon-wrap`** (icône à gauche dans l'input)
```css
position: relative
  i: position absolute, left 12px, top 50% translateY(-50%), color #64748b, font-size 15px
  .form-control: padding-left 38px
```

**`.form-section-title`**
```css
font-family: Condensed | 13px | 700 | uppercase | letter-spacing: 1px
color: #64748b | border-bottom: 2px solid #f59e0b | display: inline-block | padding-bottom: 10px | margin-bottom: 20px
```

**`.section-divider`** : `height: 1px; background: #e2e8f0; margin: 24px 0;`

**Checkboxes / switches** : `.form-check-input:checked` → `background-color: #f59e0b; border-color: #f59e0b`

---

### 5.8 Alertes — `.alert`

```css
border-radius: 10px | font-size: 13.5px | border: none
display: flex | align-items: flex-start | gap: 10px
i: flex-shrink 0, margin-top 2px, font-size 16px
```

| Variante | Fond | Texte |
|---|---|---|
| `.alert-success` | `rgba(16,185,129,.1)` | `#065f46` |
| `.alert-danger` | `rgba(239,68,68,.1)` | `#991b1b` |
| `.alert-warning` | `rgba(245,158,11,.1)` | `#92400e` |
| `.alert-info` | `rgba(59,130,246,.1)` | `#1e40af` |

Flash messages : auto-dismiss après 4500ms via Bootstrap Alert JS.

---

### 5.9 Page Header

```html
<div class="page-header">
  <div class="page-header-left">
    <h1>Titre de la page</h1>
    <p>Sous-titre descriptif</p>
  </div>
  <!-- Optionnel : bouton retour ou action principale -->
  <a href="..." class="btn btn-ghost">...</a>
</div>
```

```css
.page-header: display flex | justify-content: space-between | align-items: center
  margin-bottom: 24px | flex-wrap: wrap | gap: 12px
.page-header-left h1: Condensed 26px/700, letter-spacing .3px, margin 0 0 2px
.page-header-left p: 13.5px, color #64748b, margin 0
```

---

### 5.10 Avatars

| Type | Taille | Border-radius | Usage |
|---|---|---|---|
| `.user-avatar` | 38×38px | 50% | Tableaux utilisateurs |
| `.sidebar-avatar` | 34×34px | 50% | Footer sidebar |
| `.profile-avatar-lg` | 80×80px | 50% | Page profil |

Tous : `display flex; align-items center; justify-content center; font-family Condensed; font-weight 700; background amber-soft; color amber; border amber`.

---

### 5.11 Statistiques (KPI)

```html
<div class="stat-value">1 234</div>
<div class="stat-label">Libellé métrique</div>
```

```css
.stat-value: Condensed 24px/700, color #0f172a, line-height 1
.stat-label: 12px/600, color #64748b, uppercase, letter-spacing .7px
```

---

### 5.12 Animations

```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.fade-up          { animation: fadeUp .35s ease forwards; }
.fade-up-delay-1  { animation-delay: .05s; opacity: 0; animation-fill-mode: forwards; }
.fade-up-delay-2  { animation-delay: .10s; opacity: 0; animation-fill-mode: forwards; }
.fade-up-delay-3  { animation-delay: .15s; opacity: 0; animation-fill-mode: forwards; }
```

**Usage :** Envelopper tout le `{% block content %}` dans `<div class="fade-up">`. Les cartes secondaires utilisent `.fade-up-delay-1`, `.fade-up-delay-2`.

---

## 6. Icônes — Bootstrap Icons 1.11.3

Convention : **toujours utiliser la variante `-fill`** pour les icônes de navigation, de statut et d'action. La variante outline est réservée aux placeholders et aux icônes d'illustration.

### Mapping sémantique

| Contexte | Icône |
|---|---|
| Dashboard | `bi-grid-1x2-fill` |
| Clients | `bi-building-fill` |
| Formations (catalogue) | `bi-collection-fill` |
| Sessions | `bi-calendar3-fill` |
| Formations (nav parent) | `bi-mortarboard-fill` |
| Études / projets | `bi-diagram-3-fill` |
| Factures | `bi-receipt-cutoff` |
| Dépenses | `bi-credit-card-fill` |
| Ressources (parent) | `bi-boxes` |
| Formateurs | `bi-person-fill-check` |
| Salles | `bi-door-open-fill` |
| Équipements | `bi-tools` |
| Utilisateurs | `bi-people-fill` |
| Paramètres | `bi-gear-fill` |
| ISI / sécurité | `bi-shield-fill-check` |
| Profil / personne | `bi-person-fill` |
| Déconnexion | `bi-box-arrow-right` |
| Profil cercle | `bi-person-circle` |
| Modifier | `bi-pencil-fill` |
| Supprimer | `bi-trash-fill` |
| Ajouter | `bi-plus-lg` |
| Enregistrer / valider | `bi-check-lg` |
| Annuler / retour | `bi-arrow-left` |
| Clé / mot de passe | `bi-key-fill` |
| Email | `bi-envelope-fill` |
| Téléphone | `bi-telephone-fill` |
| Globe | `bi-globe` |
| Cadenas | `bi-lock-fill` |
| Identifiant | `bi-at` |
| Alerte erreur | `bi-exclamation-circle-fill` |
| Alerte triangle | `bi-exclamation-triangle-fill` |
| Succès | `bi-check-circle-fill` |
| Info | `bi-info-circle-fill` |
| Statut actif (point) | `bi-circle-fill` (7px) |
| Désactiver | `bi-slash-circle-fill` |
| Activer | `bi-check-circle-fill` |
| Maison breadcrumb | `bi-house-fill` |
| Chevron breadcrumb | `bi-chevron-right` |
| Menu mobile | `bi-list` |
| Téléverser / fichier | `bi-upload` |
| Document | `bi-file-earmark-text-fill` |
| Graphique | `bi-bar-chart-fill` |
| Calendrier | `bi-calendar-event-fill` |
| Participants | `bi-people-fill` |
| Attestation | `bi-patch-check-fill` |
| Phase projet | `bi-layers-fill` |
| Livrable | `bi-file-earmark-arrow-down-fill` |
| Maintenance | `bi-wrench-adjustable-fill` |
| Réservation | `bi-bookmark-fill` |

---

## 7. Structure d'un template standard

Tous les templates (hors login) héritent de `base.html` selon ce squelette :

```django
{% extends "base.html" %}

{% block title %}Titre de la page{% endblock %}

{% block breadcrumb %}
<i class="bi bi-house-fill" style="font-size:12px;"></i>
<i class="bi bi-chevron-right" style="font-size:10px;"></i>
<a href="{% url 'app:list_view' %}" style="color:var(--text-muted);text-decoration:none;">Section</a>
<i class="bi bi-chevron-right" style="font-size:10px;"></i>
{% endblock %}
{% block breadcrumb_active %}Titre courant{% endblock %}

{% block topbar_actions %}
  <a href="{% url 'app:create_view' %}" class="topbar-btn primary">
    <i class="bi bi-plus-lg"></i> Nouvel élément
  </a>
{% endblock %}

{% block content %}
<div class="fade-up">

  <!-- Page header -->
  <div class="page-header">
    <div class="page-header-left">
      <h1>Titre</h1>
      <p>Sous-titre</p>
    </div>
  </div>

  <!-- KPI row (si applicable) -->
  <div class="row g-3 mb-4">
    <div class="col-sm-3">
      <div class="isi-card">
        <div class="isi-card-body" style="display:flex;align-items:center;gap:16px;padding:18px 20px;">
          <div class="card-icon amber" style="width:44px;height:44px;font-size:20px;border-radius:12px;">
            <i class="bi bi-icon-fill"></i>
          </div>
          <div>
            <div class="stat-value">42</div>
            <div class="stat-label">Libellé</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Main content card -->
  <div class="isi-card fade-up-delay-1">
    <div class="isi-card-header">
      <div class="card-icon amber"><i class="bi bi-icon-fill"></i></div>
      <h3>Titre de la section</h3>
    </div>

    <!-- Table -->
    <div style="overflow-x:auto;">
      <table class="isi-table">
        <thead>
          <tr>
            <th>Colonne</th>
            ...
            <th style="text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for item in object_list %}
          <tr>
            <td>{{ item.field }}</td>
            ...
            <td>
              <div style="display:flex;justify-content:flex-end;gap:6px;">
                <a href="{% url 'app:detail' item.pk %}" class="btn btn-ghost btn-sm">
                  <i class="bi bi-eye-fill"></i>
                </a>
                <a href="{% url 'app:edit' item.pk %}" class="btn btn-ghost btn-sm">
                  <i class="bi bi-pencil-fill"></i>
                </a>
              </div>
            </td>
          </tr>
          {% empty %}
          <!-- Empty state -->
          <tr>
            <td colspan="N">
              <div class="text-center" style="padding:60px 24px;">
                <div style="font-size:48px;color:#e2e8f0;margin-bottom:16px;">
                  <i class="bi bi-icon"></i>
                </div>
                <p style="color:#64748b;font-size:15px;margin:0;">Aucun élément trouvé.</p>
                <a href="{% url 'app:create' %}" class="btn btn-amber mt-3">
                  <i class="bi bi-plus-lg"></i> Créer le premier
                </a>
              </div>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

</div>
{% endblock %}
```

---

## 8. Patterns récurrents

### Formulaire de création / édition
```
col-lg-8  → .isi-card avec formulaire principal
col-lg-4  → .isi-card(s) latérales (statut, actions rapides, aide)
```

- `.form-section-title` pour chaque groupe de champs
- `.section-divider` entre les groupes
- `.input-icon-wrap` sur tous les champs texte à sémantique forte (email, téléphone, url, identifiant)
- Boutons en bas : `btn-amber` (enregistrer) + `btn-ghost` (annuler), dans un `<div class="d-flex gap-2">`
- Attribut `novalidate` sur `<form>` — validation gérée côté Django

### Page de détail
```
col-lg-4  → carte identité / avatar / actions
col-lg-8  → cartes informations détaillées
```

### Empty state (état vide)
```html
<div class="text-center" style="padding:60px 24px;">
  <div style="font-size:48px;color:#e2e8f0;margin-bottom:16px;">
    <i class="bi bi-{icone-du-module}"></i>
  </div>
  <p style="color:#64748b;font-size:15px;margin:0;">Aucun {élément} trouvé.</p>
  <a href="..." class="btn btn-amber mt-3">
    <i class="bi bi-plus-lg"></i> Créer le premier {élément}
  </a>
</div>
```

### Badge de statut inline dans un tableau
```html
<span class="isi-badge {couleur}">
  <i class="bi bi-circle-fill" style="font-size:7px;"></i> Libellé statut
</span>
```

### Barre de sauvegarde sticky (formulaires settings)
```html
<div style="position:sticky;bottom:0;background:#fff;border-top:1px solid var(--card-border);padding:14px 0;margin-top:8px;z-index:100;">
  <div class="d-flex gap-2 align-items-center">
    <button type="submit" class="btn btn-amber">
      <i class="bi bi-check-lg"></i> Enregistrer les modifications
    </button>
    <span style="font-size:13px;color:#94a3b8;">
      <i class="bi bi-info-circle"></i> Les modifications sont appliquées immédiatement.
    </span>
  </div>
</div>
```

### Onglets de navigation interne (tabs settings)
```html
<div class="isi-card mb-4" style="padding:0;overflow:hidden;">
  <div style="display:flex;border-bottom:1px solid var(--card-border);">
    <a href="{% url '...' %}"
       style="padding:14px 22px;font-size:13.5px;font-weight:600;text-decoration:none;
              display:flex;align-items:center;gap:8px;
              border-bottom:2px solid {% if active %}var(--accent){% else %}transparent{% endif %};
              color:{% if active %}var(--accent){% else %}var(--text-muted){% endif %};">
      <i class="bi bi-icon-fill"></i> Label
    </a>
  </div>
</div>
```

### Preview / aperçu de fichier / image uploadé
```html
<div style="text-align:center;margin-bottom:10px;padding:10px;background:#f8fafc;
            border-radius:8px;border:1px solid var(--card-border);">
  <img src="{{ obj.field.url }}" alt="" style="max-height:60px;max-width:100%;object-fit:contain;">
</div>
```

### Hint sous un champ
```html
<div style="font-size:11.5px;color:#94a3b8;margin-top:4px;">Texte d'aide</div>
```

---

## 9. Contrôle d'accès dans les templates

```django
{% if request.user.profile.is_admin %}
  <!-- Contenu visible uniquement pour l'administrateur -->
{% endif %}
```

- Les sections financières, les rapports, les dépenses, les équipements et la gestion des utilisateurs sont systématiquement wrappées dans ce guard.
- La navigation sidebar applique le même pattern pour masquer les sections réservées.

---

## 10. Règles de style — DO / DON'T

| ✅ DO | ❌ DON'T |
|---|---|
| Hériter de `base.html` | Réécrire le head/sidebar/topbar |
| Utiliser les variables CSS `var(--...)` | Hardcoder des couleurs hex directement dans les classes |
| Mettre les icônes Bootstrap Icons via `<i class="bi bi-...">` | Utiliser d'autres librairies d'icônes |
| Wraper le contenu dans `<div class="fade-up">` | Omettre l'animation d'entrée |
| Écrire le style inline uniquement pour les overrides ponctuels | Créer des fichiers CSS séparés par template |
| Utiliser Bootstrap grid (`row`, `col-*`) | Utiliser flexbox/grid CSS custom pour la mise en page |
| Suffixer les actions colonnes tableaux avec `style="text-align:right;"` | Centrer les actions |
| Utiliser `{% url 'namespace:name' %}` | Hardcoder les URLs |
| Langue : **français** dans toute l'interface | Utiliser l'anglais dans les labels UI |
| Devise : **DA** (Dinar Algérien) | Utiliser € ou $ |
| Ajouter `novalidate` sur les `<form>` | Laisser la validation HTML5 native s'afficher |

---

## 11. Blocs Django disponibles dans `base.html`

| Bloc | Usage |
|---|---|
| `{% block title %}` | Titre de l'onglet navigateur (sans suffixe "— ISI", déjà ajouté) |
| `{% block breadcrumb %}` | Remplace entièrement le breadcrumb |
| `{% block breadcrumb_active %}` | Dernier segment du breadcrumb (texte courant) |
| `{% block topbar_actions %}` | Boutons d'action dans la barre supérieure droite |
| `{% block content %}` | Contenu principal de la page |
| `{% block extra_head %}` | CSS ou meta supplémentaires dans `<head>` |
| `{% block extra_scripts %}` | JS supplémentaires en fin de `<body>` |

---

## 12. Context processors disponibles

- `request` — accès à `request.user`, `request.user.profile`, `request.resolver_match`
- `messages` — flash messages Django
- `institute_info` — données singleton de l'institut (via `core.context_processors.institute_info`)

---

*Ce document est la source de vérité unique pour la génération de tous les templates de l'application ISI. Toute déviation doit être explicitement justifiée.*
