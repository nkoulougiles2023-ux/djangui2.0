# DJANGUI 2.0 — Spécification Technique Complète

## Application de Tontine, Épargne, Prêt Instantané & Investissement — Marché Camerounais

---

# TABLE DES MATIÈRES

1. Vision & Concept
2. Acteurs du Système
3. Modèle Économique
4. Modèles de Données (14 entités)
5. Relations & Index
6. Flux Utilisateur (14 flux détaillés)
7. Endpoints API
8. Règles Métier & Calculs Financiers
9. Sécurité & Architecture
10. Conformité Réglementaire Cameroun
11. Tâches Asynchrones (Celery)
12. Stack Technique
13. Prompt pour Claude Code

---

# 1. VISION & CONCEPT

DJANGUI 2.0 est une application de prêt instantané, tontine et épargne destinée au marché camerounais. Son mécanisme central : les prêts sont sécurisés à 100% par des avalistes (garants) qui bloquent une partie de leur argent. L'application facture une commission de 10% répartie entre 3 acteurs.

L'objectif est de répondre au besoin brutal d'accès au crédit instantané au Cameroun, en s'appuyant sur la culture communautaire des tontines et la pression sociale comme mécanisme de sécurisation.

---

# 2. ACTEURS DU SYSTÈME

## Emprunteur
- Demande un prêt
- Rembourse le capital + 10% de commission
- Gagne des points "Tchekele" s'il paie à temps
- Doit avoir le KYC validé et un score de réputation ≥ 20

## Avaliste (Garant)
- Bloque un montant équivalent au prêt demandé pour le sécuriser
- Si l'emprunteur fait défaut, l'avaliste paie
- Reçoit 3% de commission en récompense du risque pris
- Doit avoir le KYC validé
- Maximum 3 garanties actives simultanément

## Prêteur (Investisseur)
- Fournit des fonds à la plateforme pour augmenter la liquidité
- Ne prend pas de risque direct (les avalistes couvrent)
- Rémunéré à 3% sur les revenus générés (modèle partage des revenus)
- KYC obligatoire

## Plateforme DJANGUI 2.0
- Prend 4% de commission pour la gestion
- Gère le fonds de réserve, le marketing, le développement

---

# 3. MODÈLE ÉCONOMIQUE

## Répartition de la commission (10% par prêt)

| Bénéficiaire | Part | Sur 15 000 FCFA | Sur 100 000 FCFA |
|---|---|---|---|
| DJANGUI 2.0 (plateforme) | 4% | 600 FCFA | 4 000 FCFA |
| Prêteur (investisseur pool) | 3% | 450 FCFA | 3 000 FCFA |
| Avaliste (garant) | 3% | 450 FCFA | 3 000 FCFA |
| **Total** | **10%** | **1 500 FCFA** | **10 000 FCFA** |

## Utilisation des fonds des prêteurs
- Fonds de réserve pour impayés exceptionnels
- Investissements à faible risque (comptes à terme)
- Financement marketing
- Prêts à d'autres acteurs économiques via partenariats

## Commission tontine (suggestion)
- 2% de la cagnotte prélevé par la plateforme à chaque tour

---

# 4. MODÈLES DE DONNÉES

## 4.1 USER (Utilisateur)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK, auto-généré |
| phone | CharField(15) | unique, obligatoire, format +237XXXXXXXXX |
| email | EmailField | unique, nullable |
| password | CharField(128) | hashé |
| first_name | CharField(100) | obligatoire |
| last_name | CharField(100) | obligatoire |
| date_of_birth | DateField | obligatoire, âge ≥ 18 ans |
| gender | CharField(1) | choix : M / F |
| address | TextField | obligatoire |
| city | CharField(100) | obligatoire |
| photo_profile | ImageField | nullable |
| cni_number | CharField(20) | unique, nullable |
| cni_front_image | ImageField | nullable |
| cni_back_image | ImageField | nullable |
| selfie_kyc | ImageField | nullable |
| kyc_status | CharField(20) | choix : pending / verified / rejected, défaut pending |
| is_active | BooleanField | défaut True |
| is_banned | BooleanField | défaut False |
| reputation_score | IntegerField | défaut 50, min 0, max 100 |
| tchekele_points | IntegerField | défaut 0, min 0 |
| pin_code | CharField(128) | hashé avec bcrypt, 4 chiffres |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |

Contraintes métier :
- Un utilisateur peut être simultanément emprunteur, avaliste ET prêteur (rôle dynamique selon l'action)
- Impossible d'emprunter si kyc_status ≠ verified
- Impossible d'emprunter si reputation_score < 20
- Impossible d'être avaliste si kyc_status ≠ verified
- Un numéro de téléphone = un seul compte
- Un numéro CNI = un seul compte

## 4.2 WALLET (Portefeuille)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| user | OneToOneField→User | unique, cascade delete |
| available_balance | DecimalField(12,2) | défaut 0, min 0 |
| blocked_balance | DecimalField(12,2) | défaut 0, min 0 |
| currency | CharField(5) | défaut XAF |
| updated_at | DateTimeField | auto_now |

Contraintes métier :
- Créé automatiquement à l'inscription (signal post_save sur User)
- available_balance ne peut jamais passer en négatif
- blocked_balance est incrémenté quand l'utilisateur garantit un prêt
- Toute modification de solde DOIT passer par une Transaction

## 4.3 LOAN (Prêt)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| borrower | ForeignKey→User | obligatoire, related_name='loans_as_borrower' |
| amount | DecimalField(12,2) | obligatoire, min 1000 FCFA |
| commission_rate | DecimalField(4,2) | défaut 10.00 |
| commission_amount | DecimalField(12,2) | calculé : amount × commission_rate / 100 |
| total_to_repay | DecimalField(12,2) | calculé : amount + commission_amount |
| duration_days | IntegerField | obligatoire, choix : 7 / 14 / 30 / 60 / 90 |
| status | CharField(20) | voir statuts ci-dessous |
| requested_at | DateTimeField | auto_now_add |
| approved_at | DateTimeField | nullable |
| due_date | DateTimeField | calculé : approved_at + duration_days |
| completed_at | DateTimeField | nullable |
| amount_repaid | DecimalField(12,2) | défaut 0 |
| grace_period_hours | IntegerField | défaut 72 |

Statuts : waiting_guarantor → waiting_validation → active → repaid | defaulted | cancelled

Contraintes métier :
- Un emprunteur ne peut avoir qu'UN SEUL prêt actif à la fois
- Le montant max dépend du reputation_score (voir grille section 8)
- Le prêt passe à active que quand la garantie couvre 100% du montant
- Premier prêt d'un utilisateur plafonné à 15 000 FCFA peu importe le score
- Cooldown de 24h entre deux prêts consécutifs
- Expiration automatique après 48h sans avaliste → cancelled

## 4.4 GUARANTEE (Garantie / Avalisme)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| loan | ForeignKey→Loan | obligatoire, related_name='guarantees' |
| guarantor | ForeignKey→User | obligatoire, related_name='guarantees_given' |
| amount_blocked | DecimalField(12,2) | obligatoire |
| status | CharField(20) | choix : blocked / released / seized |
| commission_earned | DecimalField(12,2) | défaut 0 |
| blocked_at | DateTimeField | auto_now_add |
| released_at | DateTimeField | nullable |

Contraintes métier :
- guarantor ≠ loan.borrower (JAMAIS avaliste de soi-même)
- Somme des amount_blocked de toutes les garanties d'un prêt ≥ loan.amount
- Un avaliste ne peut bloquer que ≤ 80% de son wallet.available_balance
- Max 3 prêts garantis simultanément par avaliste
- Un emprunteur ne peut pas avoir le même avaliste pour plus de 2 prêts consécutifs
- Au remboursement : status → released, commission_earned = loan.commission_amount × 0.30
- En défaut : status → seized, amount_blocked transféré

## 4.5 LOAN_REPAYMENT (Remboursement)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| loan | ForeignKey→Loan | obligatoire, related_name='repayments' |
| amount | DecimalField(12,2) | obligatoire, min 100 FCFA |
| paid_at | DateTimeField | auto_now_add |
| payment_method | CharField(20) | choix : wallet / mtn_momo / orange_money |
| transaction | OneToOneField→Transaction | référence |

Contraintes métier :
- Chaque remboursement déclenche le recalcul de loan.amount_repaid
- Quand amount_repaid ≥ total_to_repay → prêt passe à repaid + distribution commissions
- Remboursement partiel autorisé

## 4.6 INVESTMENT (Investissement)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| investor | ForeignKey→User | obligatoire, related_name='investments' |
| amount | DecimalField(12,2) | obligatoire, min 5000 FCFA |
| status | CharField(20) | choix : active / withdrawn |
| return_rate | DecimalField(4,2) | défaut 3.00 |
| total_returns_earned | DecimalField(12,2) | défaut 0 |
| invested_at | DateTimeField | auto_now_add |
| withdrawn_at | DateTimeField | nullable |
| notice_period_days | IntegerField | défaut 7 |

Contraintes métier :
- Retrait avec préavis de notice_period_days
- Rendements calculés mensuellement via tâche Celery
- KYC obligatoire

## 4.7 TRANSACTION (Journal financier)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| type | CharField(30) | voir types ci-dessous |
| amount | DecimalField(12,2) | obligatoire, toujours positif |
| sender | ForeignKey→User | nullable |
| receiver | ForeignKey→User | nullable |
| loan | ForeignKey→Loan | nullable |
| tontine | ForeignKey→Tontine | nullable |
| status | CharField(20) | pending / completed / failed |
| payment_reference | CharField(100) | nullable, réf Mobile Money |
| idempotency_key | CharField(36) | unique, UUID généré côté client |
| description | TextField | nullable |
| created_at | DateTimeField | auto_now_add |

Types : deposit, withdrawal, loan_disbursement, loan_repayment, guarantee_block, guarantee_release, guarantee_seize, commission_platform, commission_guarantor, commission_investor, tontine_contribution, tontine_payout, investment_deposit, investment_withdrawal, investment_return, tchekele_reward

Contraintes métier :
- Les transactions sont IMMUTABLES : jamais d'update, jamais de delete
- Pour annuler → créer une transaction inverse
- Toute transaction doit être atomique (transaction.atomic())
- idempotency_key empêche les doubles exécutions

## 4.8 TONTINE

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| name | CharField(100) | obligatoire |
| creator | ForeignKey→User | obligatoire |
| contribution_amount | DecimalField(12,2) | obligatoire, min 500 FCFA |
| frequency | CharField(20) | choix : weekly / biweekly / monthly |
| max_members | IntegerField | obligatoire, min 2, max 50 |
| current_round | IntegerField | défaut 1 |
| status | CharField(20) | recruiting / active / completed / cancelled |
| requires_guarantor | BooleanField | défaut True |
| start_date | DateField | nullable, fixée quand groupe complet |
| created_at | DateTimeField | auto_now_add |

Contraintes métier :
- Ne démarre (active) que quand max_members est atteint
- Nombre de tours = max_members
- Cagnotte par tour = contribution_amount × max_members

## 4.9 TONTINE_MEMBERSHIP (Adhésion)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| tontine | ForeignKey→Tontine | obligatoire |
| member | ForeignKey→User | obligatoire |
| guarantor | ForeignKey→User | nullable |
| position | IntegerField | ordre dans le tour |
| has_received_pot | BooleanField | défaut False |
| joined_at | DateTimeField | auto_now_add |

Contrainte unique : (tontine, member)

Contraintes métier :
- guarantor ≠ member
- Si requires_guarantor = True, adhésion refusée sans guarantor
- Le guarantor doit avoir un solde ≥ contribution_amount

## 4.10 TONTINE_CONTRIBUTION (Cotisation)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| tontine | ForeignKey→Tontine | obligatoire |
| member | ForeignKey→User | obligatoire |
| round_number | IntegerField | obligatoire |
| amount | DecimalField(12,2) | = tontine.contribution_amount |
| paid | BooleanField | défaut False |
| paid_at | DateTimeField | nullable |
| transaction | ForeignKey→Transaction | nullable |

Contrainte unique : (tontine, member, round_number)

## 4.11 NOTIFICATION

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| user | ForeignKey→User | obligatoire |
| type | CharField(30) | loan_reminder / loan_approved / loan_defaulted / guarantee_request / guarantee_seized / tontine_turn / tontine_reminder / tchekele_earned / system |
| title | CharField(200) | obligatoire |
| message | TextField | obligatoire |
| is_read | BooleanField | défaut False |
| created_at | DateTimeField | auto_now_add |

## 4.12 HONOR_BOARD (Mbo — Tableau d'honneur)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| user | ForeignKey→User | obligatoire |
| period | CharField(7) | format YYYY-MM |
| score | IntegerField | calculé |
| rank | IntegerField | calculé |
| is_visible | BooleanField | défaut True |

Contrainte unique : (user, period)
Recalculé mensuellement via tâche Celery.

## 4.13 PARTNER (Partenaire)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| name | CharField(200) | obligatoire |
| type | CharField(30) | bayam_sellam / market / training / lottery / other |
| discount_description | TextField | description avantage |
| tchekele_cost | IntegerField | coût en points |
| is_active | BooleanField | défaut True |
| contact_phone | CharField(15) | nullable |
| city | CharField(100) | obligatoire |

## 4.14 PLATFORM_ACCOUNT (Compte Plateforme)

| Champ | Type | Contraintes |
|---|---|---|
| id | UUID | PK |
| type | CharField(30) | commission / reserve_fund / investment_pool |
| balance | DecimalField(14,2) | défaut 0 |
| updated_at | DateTimeField | auto_now |

---

# 5. RELATIONS & INDEX

## Diagramme des relations

```
User ──── 1:1 ──── Wallet
  │
  ├── 1:N ──── Loan (as borrower)
  │               └── 1:N ──── Guarantee (avalistes du prêt)
  │               └── 1:N ──── LoanRepayment
  │
  ├── 1:N ──── Guarantee (as guarantor)
  ├── 1:N ──── Investment (as investor)
  ├── 1:N ──── Transaction (as sender / receiver)
  ├── 1:N ──── Notification
  ├── 1:N ──── HonorBoard
  │
  ├── 1:N ──── TontineMembership (as member)
  ├── 1:N ──── TontineMembership (as guarantor)
  └── 1:N ──── Tontine (as creator)
                  └── 1:N ──── TontineMembership
                  └── 1:N ──── TontineContribution
```

## Index recommandés

- User.phone — recherche à la connexion
- Loan.borrower + Loan.status — index composé (prêts actifs)
- Guarantee.guarantor + Guarantee.status — garanties actives
- Transaction.sender, Transaction.receiver, Transaction.created_at — historique
- Transaction.idempotency_key — vérification unicité
- TontineContribution.tontine + TontineContribution.round_number — cotisations d'un tour
- Notification.user + Notification.is_read — notifications non lues

---

# 6. FLUX UTILISATEUR

## FLUX 0 — Inscription & KYC

### Écran 0.1 — Splash / Bienvenue
- Logo DJANGUI 2.0, slogan
- Boutons : "Créer un compte" / "Se connecter"

### Écran 0.2 — Inscription étape 1 : téléphone
- Champ : numéro (+237)
- Validation : format camerounais 9 chiffres, numéro non utilisé
- Action : envoi OTP SMS

### Écran 0.3 — Vérification OTP
- Code à 6 chiffres
- Validation : correct, non expiré (5 min), max 3 tentatives
- Lien "Renvoyer" (cooldown 60s)

### Écran 0.4 — Inscription étape 2 : infos personnelles
- Champs : prénom, nom, date naissance, genre, ville, adresse
- Validation : tous obligatoires, âge ≥ 18

### Écran 0.5 — Création du PIN
- PIN 4 chiffres + confirmation
- Validation : correspondance, pas de séquence triviale (0000, 1234)

### Écran 0.6 — KYC (optionnel à l'inscription, obligatoire avant 1er prêt)
- Upload recto/verso CNI + selfie + numéro CNI
- Statut → pending

Résultat : wallet créé avec solde 0. L'utilisateur peut explorer mais ne peut ni emprunter ni être avaliste sans KYC verified.

## FLUX 1 — Connexion

### Écran 1.1 — Login par OTP
- Champ : téléphone → envoi OTP → vérification

### Écran 1.2 — Login rapide par PIN
- Champ : téléphone + PIN 4 chiffres

## FLUX 2 — Dashboard (Accueil)

### Écran 2.1 — Écran principal
- En-tête : photo, prénom, badge KYC, points Tchekele
- Carte Wallet : solde disponible, solde bloqué, boutons Déposer/Retirer
- Actions rapides (4 boutons) : Demander un prêt, Devenir avaliste, Tontines, Investir
- Mon prêt en cours (si existe) : montant, échéance, progression, bouton Rembourser
- Mes garanties actives : nombre, montant bloqué
- 3 dernières notifications
- Mbo du mois : top 3

## FLUX 3 — Dépôt (Mobile Money → Wallet)

### Écran 3.1 — Choix du moyen
- MTN Mobile Money / Orange Money

### Écran 3.2 — Montant
- Validation : min 500 FCFA, max 500 000 FCFA/transaction

### Écran 3.3 — Confirmation PIN
- PIN 4 chiffres, max 3 tentatives

### Écran 3.4 — En attente de paiement
- Message "Validez sur votre téléphone", timeout 2 min

### Écran 3.5 — Résultat
- Succès : wallet mis à jour, Transaction completed
- Échec : Transaction failed, réessayer

## FLUX 4 — Retrait (Wallet → Mobile Money)

Même structure que le dépôt en sens inverse.
- Validation : min 500 FCFA, max = available_balance
- Pas de retrait sur le blocked_balance

## FLUX 5 — Demande de prêt

### Écran 5.1 — Vérifications automatiques
- KYC vérifié ? Pas de prêt actif ? Score ≥ 20 ? Cooldown 24h respecté ?
- Si non → message d'erreur explicite + lien vers l'action corrective

### Écran 5.2 — Formulaire de demande
- Montant : slider ou saisie, min 1000, max selon score (affiché dynamiquement)
- Durée : 7 / 14 / 30 / 60 / 90 jours
- Récapitulatif temps réel : montant, commission 10%, total à rembourser, échéance estimée

### Écran 5.3 — Confirmation
- Résumé complet, checkbox CGU, confirmation PIN
- Prêt créé en statut waiting_guarantor

### Écran 5.4 — En attente d'avaliste
- Timer : expire après 48h → cancelled
- Option "Inviter un avaliste" (partage SMS/WhatsApp)
- Possibilité d'annuler

## FLUX 6 — Devenir avaliste

### Écran 6.1 — Liste des prêts à garantir
- Prêts en waiting_guarantor
- Carte : prénom emprunteur, montant, durée, score réputation
- Filtres : montant, durée. Tri : score décroissant, date

### Écran 6.2 — Détail du prêt
- Infos complètes + commission estimée (3%)
- Profil emprunteur : score, historique prêts
- Avertissement risque de saisie
- Vérifications : KYC verified, solde suffisant, < 3 garanties actives, pas l'emprunteur

### Écran 6.3 — Confirmation de garantie
- Résumé montant bloqué + commission estimée
- Confirmation PIN
- Création Guarantee (blocked), mise à jour wallet
- Si couverture 100% : prêt → active, versement à l'emprunteur
- Notifications envoyées

## FLUX 7 — Remboursement

### Écran 7.1 — Mon prêt en cours
- Total, déjà remboursé, reste, échéance, jours restants, barre progression

### Écran 7.2 — Remboursement
- Montant pré-rempli (reste à payer), modifiable pour partiel
- Validation : min 100 FCFA, max = reste à payer
- Source : wallet ou Mobile Money
- Confirmation PIN

### Écran 7.3 — Résultat
- Partiel : mise à jour reste
- Complet : prêt → repaid, commissions distribuées, avaliste débloqué, Tchekele attribués, score +5/+2, message félicitations

## FLUX 8 — Défaut de paiement (automatique via Celery)

1. Vérifier prêts active dont due_date dépassée
2. Si dans période de grâce (72h) : notifications rappel emprunteur + avaliste
3. Si grâce dépassée :
   - Prêt → defaulted
   - Guarantee → seized
   - Montant saisi couvre le restant
   - Commissions distribuées (avaliste reçoit 0)
   - Score emprunteur -20
   - Notifications emprunteur + avaliste

## FLUX 9 — Tontine

### Écran 9.1 — Liste des tontines
- Onglets : Mes tontines / Rejoindre
- Carte : nom, cotisation, fréquence, membres X/Y, statut

### Écran 9.2 — Créer une tontine
- Champs : nom, cotisation (min 500), fréquence, nb membres (2-50), avaliste requis (oui/non)
- Créateur inscrit automatiquement en position 1
- Statut : recruiting
- Option inviter (SMS/WhatsApp)

### Écran 9.3 — Rejoindre
- Détail tontine + places restantes
- Si avaliste requis : sélection d'un avaliste
- Validation : wallet suffisant pour 1 cotisation, KYC vérifié
- Confirmation PIN

### Écran 9.4 — Tontine en cours
- Tour actuel, bénéficiaire, liste membres avec statut cotisation
- Bouton Cotiser (montant fixe, PIN)
- Quand tous cotisent → cagnotte versée → tour suivant

### Écran 9.5 — Défaut cotisation
- Délai max 48h, puis prélèvement avaliste ou exclusion + pénalité score -10

## FLUX 10 — Investir

### Écran 10.1 — Espace investisseur
- Résumé : total investi, rendements accumulés, graphique mensuel
- Boutons : Investir / Retirer

### Écran 10.2 — Nouveau dépôt
- Montant min 5 000 FCFA, explication rendement, confirmation PIN

### Écran 10.3 — Retrait
- Montant max = investi, préavis 7 jours, confirmation PIN

## FLUX 11 — Tchekele & Récompenses

### Écran 11.1 — Mes Tchekele
- Solde, historique gains/dépenses

### Écran 11.2 — Boutique
- Partenaires, avantages, coût en Tchekele
- Bouton Échanger → code promo / QR code

## FLUX 12 — Notifications

### Écran 12.1 — Centre de notifications
- Liste chronologique, badge non lues, icônes par type
- Tap → redirige vers l'écran concerné

## FLUX 13 — Profil & Paramètres

### Écran 13.1 — Mon profil
- Infos, score, stats (prêts remboursés, tontines, montant garanti)

### Écran 13.2 — Paramètres
- Changer PIN, notifications push on/off, rappels SMS on/off
- Langue (FR/EN), CGU, confidentialité
- Supprimer compte (impossible si prêt actif ou garantie en cours)
- Contacter support

## FLUX 14 — Administration (Back-office)

Via Django Admin ou dashboard custom :
- Validation KYC : file d'attente, visualisation CNI+selfie, approuver/rejeter
- Monitoring prêts : par statut, alertes échéances, déclenchement défaut manuel
- Gestion tontines : vue d'ensemble, intervention litiges
- Tableau financier : commissions, fonds réserve, pool investisseurs, transactions suspectes
- Gestion utilisateurs : recherche, suspension, bannissement, historique
- Gestion partenaires : CRUD

---

# 7. ENDPOINTS API

| Domaine | Endpoint | Méthode | Description |
|---|---|---|---|
| Auth | /auth/register | POST | Inscription |
| Auth | /auth/otp/send | POST | Envoyer OTP |
| Auth | /auth/otp/verify | POST | Vérifier OTP |
| Auth | /auth/login/pin | POST | Connexion par PIN |
| Auth | /auth/token/refresh | POST | Refresh JWT |
| User | /users/me | GET/PUT | Profil |
| User | /users/me/kyc | POST | Soumettre KYC |
| User | /users/me/pin | PUT | Changer PIN |
| User | /users/me/stats | GET | Statistiques |
| Wallet | /wallet | GET | Voir solde |
| Wallet | /wallet/deposit | POST | Dépôt MoMo |
| Wallet | /wallet/withdraw | POST | Retrait MoMo |
| Wallet | /wallet/transactions | GET | Historique |
| Loans | /loans | POST | Demander un prêt |
| Loans | /loans/mine | GET | Mes prêts |
| Loans | /loans/available | GET | Prêts à garantir |
| Loans | /loans/{id} | GET | Détail prêt |
| Loans | /loans/{id}/repay | POST | Rembourser |
| Loans | /loans/{id}/cancel | DELETE | Annuler |
| Guarantees | /loans/{id}/guarantee | POST | Garantir un prêt |
| Guarantees | /guarantees/mine | GET | Mes garanties |
| Tontines | /tontines | POST/GET | Créer/Lister |
| Tontines | /tontines/{id} | GET | Détail |
| Tontines | /tontines/{id}/join | POST | Rejoindre |
| Tontines | /tontines/{id}/contribute | POST | Cotiser |
| Investments | /investments | POST/GET | Investir/Lister |
| Investments | /investments/{id}/withdraw | POST | Retirer |
| Tchekele | /tchekele | GET | Solde + historique |
| Tchekele | /tchekele/redeem | POST | Échanger |
| Notifications | /notifications | GET | Lister |
| Notifications | /notifications/{id}/read | PUT | Marquer lue |
| Honor Board | /honor-board | GET | Classement (?period=YYYY-MM) |
| Admin | /admin/kyc/pending | GET | KYC en attente |
| Admin | /admin/kyc/{id}/validate | PUT | Valider/rejeter KYC |
| Admin | /admin/loans | GET | Tous les prêts |
| Admin | /admin/dashboard | GET | Tableau de bord |
| Admin | /admin/users | GET | Tous les utilisateurs |
| Admin | /admin/users/{id} | GET/PUT | Détail/modifier user |
| Webhooks | /webhooks/mtn-momo | POST | Callback MTN MoMo |
| Webhooks | /webhooks/orange-money | POST | Callback Orange Money |

---

# 8. RÈGLES MÉTIER & CALCULS FINANCIERS

## 8.1 Scoring de réputation

Score initial : 50/100

### Gains

| Événement | Points |
|---|---|
| Prêt remboursé avant échéance | +10 |
| Prêt remboursé à temps (avant fin grâce) | +5 |
| Prêt remboursé pendant la grâce | +2 |
| Tour de tontine cotisé à temps | +3 |
| KYC validé (1ère fois) | +5 |
| 5 prêts consécutifs sans retard (streak) | +15 |
| Être avaliste d'un prêt réussi | +2 |

### Pertes

| Événement | Points |
|---|---|
| Prêt en défaut | -20 |
| Cotisation tontine en retard (payée après rappel) | -5 |
| Cotisation tontine non payée (avaliste prélevé) | -15 |
| Annulation prêt après validation avaliste | -3 |
| Signalement vérifié par admin | -10 |

Plafond : 100. Plancher : 0. Score 0 = suspendu des prêts et tontines.

## 8.2 Grille montants de prêt

| Score | Montant max | Durée max |
|---|---|---|
| 0 – 19 | Interdit | — |
| 20 – 39 | 10 000 FCFA | 14 jours |
| 40 – 54 | 50 000 FCFA | 30 jours |
| 55 – 69 | 100 000 FCFA | 60 jours |
| 70 – 84 | 200 000 FCFA | 60 jours |
| 85 – 94 | 350 000 FCFA | 90 jours |
| 95 – 100 | 500 000 FCFA | 90 jours |

Premier prêt TOUJOURS plafonné à 15 000 FCFA.

## 8.3 Formules de calcul

### Commission sur un prêt

```
commission_totale = montant_pret × 0.10
total_a_rembourser = montant_pret + commission_totale

part_plateforme = commission_totale × 0.40    (4% du prêt)
part_investisseurs = commission_totale × 0.30  (3% du prêt)
part_avaliste = commission_totale × 0.30       (3% du prêt)
```

Commissions versées UNIQUEMENT au remboursement complet.

### En cas de défaut avec saisie

```
reste_a_payer = total_a_rembourser - montant_deja_rembourse
montant_saisi = min(reste_a_payer, guarantee.amount_blocked)

part_plateforme = commission_totale × 0.40   (versée)
part_investisseurs = commission_totale × 0.30 (versée)
part_avaliste = 0  (saisi, pas de commission)
```

### Remboursement partiel

Affectation : d'abord au capital, ensuite à la commission. Distribution uniquement à la clôture.

### Rendements investisseurs (calcul mensuel)

```
pool_investisseurs_du_mois = somme de toutes les part_investisseurs du mois

pour chaque investisseur actif :
    poids = investisseur.amount / total_investissements_actifs
    rendement = pool_investisseurs_du_mois × poids
    investisseur.total_returns_earned += rendement
    → Transaction investment_return créée
```

### Tontine

```
cagnotte_par_tour = contribution_amount × nombre_de_membres
commission_tontine = cagnotte_par_tour × 0.02
montant_verse = cagnotte_par_tour - commission_tontine
nombre_de_tours = nombre_de_membres
```

Ordre de passage : aléatoire au lancement, immuable ensuite.

## 8.4 Règles anti-fraude

| Règle | Implémentation |
|---|---|
| Pas avaliste de soi-même | guarantor ≠ loan.borrower (contrainte DB + API) |
| Max 3 garanties actives | COUNT(guarantees WHERE status=blocked) < 3 |
| Blocage max 80% du solde | amount_blocked ≤ available_balance × 0.80 |
| 1 seul prêt actif | COUNT(loans WHERE status IN (active, defaulted)) == 0 |
| Limite dépôt jour | 500 000 FCFA/jour |
| Limite retrait jour | 300 000 FCFA/jour |
| Cooldown entre prêts | 24h après remboursement complet |
| Anti-collusion | Même avaliste max 2 prêts consécutifs pour 1 emprunteur |
| Téléphone unique | 1 numéro = 1 compte |
| Premier prêt plafonné | Max 15 000 FCFA peu importe le score |

## 8.5 Gestion du wallet — Invariant

```
wallet.available_balance =
    SUM(transactions entrantes completed)
  - SUM(transactions sortantes completed)
  - wallet.blocked_balance
```

Toutes les opérations sont atomiques (transaction.atomic() + select_for_update()).

## 8.6 Points Tchekele

### Gains
- Prêt remboursé à temps : +10
- Prêt remboursé en avance : +20
- Cotisation tontine à temps : +5
- Streak 5 prêts consécutifs : +50

### Dépenses (exemples)
- Réduction Bayam Sellam : 100 points
- Accès formation : 200 points
- Ticket loterie : 50 points

Les Tchekele n'ont PAS de valeur monétaire directe. Pas de conversion en FCFA.

## 8.7 Périodes et échéances

| Élément | Durée |
|---|---|
| Expiration demande prêt sans avaliste | 48h |
| Période de grâce | 72h après due_date |
| Rappels avant échéance | J-3, J-1, J-0 |
| Rappels pendant grâce | Toutes les 24h |
| Préavis retrait investisseur | 7 jours |
| Cooldown entre prêts | 24h |
| Expiration OTP | 5 min |
| Blocage après 3 PIN incorrects | 30 min |
| Délai cotisation tontine | 48h max |
| Recalcul Mbo | 1er du mois |
| Calcul rendements | 1er du mois |
| Réconciliation wallets | Chaque nuit 03h00 |

---

# 9. SÉCURITÉ & ARCHITECTURE

## 9.1 Authentification

### OTP SMS
- Code 6 chiffres, hashé dans Redis, TTL 5 min
- Max 3 tentatives par OTP
- Max 5 demandes OTP/heure/numéro
- Rate limiting : 10 req/min/IP sur /auth/otp/send

### PIN transactionnel
- 4 chiffres, hashé bcrypt (coût ≥ 12)
- 3 tentatives max → blocage 30 min (Redis)
- 5 blocages/jour → compte verrouillé (support uniquement)

### JWT
- Access token : 15 min
- Refresh token : 7 jours, rotation à chaque usage
- Blacklist tokens révoqués via Redis
- Stockage client : secure storage natif (Keychain/Keystore)

## 9.2 Protection des données

### Chiffrement
- HTTPS TLS 1.2+ obligatoire partout
- Données sensibles (CNI, images KYC) : AES-256, clé séparée (env var ou vault)
- PIN : bcrypt, coût ≥ 12
- Mots de passe (si ajoutés) : Argon2 ou bcrypt

### Protection API

| Attaque | Protection |
|---|---|
| Injection SQL | Django ORM (requêtes paramétrées), jamais raw() |
| XSS | DRF renvoie JSON, pas HTML |
| CSRF | Désactivé pour API REST (JWT stateless) |
| Brute force | Rate limiting : 5 tentatives/min login, 3/min PIN |
| IDOR | Vérification request.user == objet.owner systématique |
| Mass assignment | Serializers DRF avec fields explicites |
| File upload | Validation MIME, max 5 Mo, stockage hors web |

### Audit trail
- Log de chaque action sensible : timestamp, user_id, action, IP, user_agent, details
- Logs immutables (append-only), stockage séparé
- Rétention minimum 5 ans

## 9.3 Sécurité des transactions

### Atomicité
```python
from django.db import transaction

with transaction.atomic():
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.available_balance < amount:
        raise InsufficientFunds()
    wallet.available_balance -= amount
    wallet.save()
    Transaction.objects.create(...)
```

select_for_update() pose un verrou sur la ligne du wallet (anti double dépense).

### Idempotence
- Chaque requête de transaction inclut un idempotency_key (UUID côté client)
- Même clé en < 24h → réponse de la 1ère exécution sans re-exécuter

### Réconciliation
- Tâche Celery nocturne vérifie chaque wallet
- Si solde_calculé ≠ available_balance + blocked_balance → alerte admin + wallet gelé

## 9.4 KYC

- Images stockées chiffrées AES-256 dans bucket séparé
- Phase 1 (MVP) : validation manuelle par admin
- Phase 2 : OCR + comparaison faciale (Smile Identity)
- 1 numéro CNI = 1 seul compte
- Images supprimées 6 mois après validation
- Max 3 soumissions, après → support

## 9.5 Intégration Mobile Money

### Architecture
```
App → API DJANGUI → Microservice paiement (isolé) → API MTN MoMo / Orange Money
```

### Webhooks
- Vérification signature HMAC ou IP whitelistée
- Ne JAMAIS créditer un wallet sur la base du frontend
- Polling en fallback si webhook absent après 2 min

### Clés API
- Variables d'environnement ou vault (jamais dans le code)
- Rotation tous les 90 jours

## 9.6 Plan de sécurité — Couches

```
COUCHE 1 — Réseau
├── HTTPS/TLS 1.3
├── Firewall (ports 80/443 uniquement)
├── Protection DDoS (Cloudflare)
└── IP whitelistée pour admin

COUCHE 2 — Application
├── Rate limiting tous endpoints
├── Validation entrées (serializers DRF stricts)
├── CORS domaines autorisés uniquement
├── Headers sécurité (X-Content-Type-Options, X-Frame-Options, CSP)
└── Audit dépendances (pip-audit, dependabot)

COUCHE 3 — Authentification
├── OTP SMS hashé + TTL
├── JWT rotation refresh tokens
├── PIN bcrypt
├── Blocage tentatives échouées
└── Logs connexions

COUCHE 4 — Données
├── AES-256 données sensibles
├── TLS en transit
├── Backups quotidiens chiffrés
├── Séparation données KYC
└── select_for_update() opérations financières

COUCHE 5 — Monitoring
├── Réconciliation nocturne wallets
├── Alertes transactions anormales
├── Audit trail immutable
├── Logs centralisés (ELK)
└── Alertes admin temps réel (Telegram/email)
```

---

# 10. CONFORMITÉ RÉGLEMENTAIRE CAMEROUN

## 10.1 COBAC (Commission Bancaire Afrique Centrale)

Option 1 — Agrément EMF : nécessaire si DJANGUI prête directement. Lourd (capital minimum, reporting, audit).

Option 2 — Plateforme intermédiaire (marketplace) : DJANGUI met en relation, ne prête pas. Plus léger réglementairement.

Recommandation : commencer en Option 2 (MVP), évoluer vers Option 1 avec le volume. Consulter un cabinet juridique camerounais spécialisé fintech.

## 10.2 Protection des données personnelles

Loi n°2024-017 :
- Consentement explicite (pas pré-coché)
- Droit d'accès : copie de toutes les données sur demande
- Droit de suppression (sauf obligations légales 5 ans pour données financières)
- Politique de confidentialité en français dans l'app

## 10.3 Lutte anti-blanchiment (AML)

- KYC obligatoire
- Surveillance transactions suspectes (montants anormaux, fréquence, structuring)
- Signalement ANIF en cas de suspicion
- Conservation données 5 ans minimum

## 10.4 Fiscalité

- Immatriculation au Cameroun (registre commerce + contribuable)
- TVA 19,25% sur les commissions
- IS sur les bénéfices
- IRCM potentiel sur revenus investisseurs

---

# 11. TÂCHES CELERY

| Tâche | Fréquence | Action |
|---|---|---|
| check_loan_expiry | Toutes les heures | Annule demandes sans avaliste après 48h |
| check_loan_default | Toutes les heures | Vérifie échéances, rappels, saisies |
| send_loan_reminders | Quotidienne | Rappels J-3, J-1, J-0 |
| check_tontine_contributions | Toutes les 6h | Cotisations en retard, relance/prélèvement |
| calculate_monthly_returns | 1er du mois | Rendements investisseurs |
| update_honor_board | 1er du mois | Classement Mbo |
| reconcile_wallets | Chaque nuit 03h00 | Intégrité des soldes |
| cleanup_expired_otps | Toutes les 15 min | Nettoyage Redis |
| generate_daily_report | Chaque nuit 06h00 | Rapport admin volumes/commissions/alertes |
| check_suspicious_activity | Toutes les heures | Détection fraude |

---

# 12. STACK TECHNIQUE

## Backend
- Django 5.x + Django REST Framework
- PostgreSQL (base de données principale)
- Redis (cache, OTP, sessions, compteurs rate limiting, blacklist JWT)
- Celery + Redis (tâches asynchrones)

## Frontend mobile
- React Native ou Flutter (Android prioritaire au Cameroun)
- Alternative budget serré : Progressive Web App (PWA)

## Paiements
- MTN MoMo API
- Orange Money API
- Microservice paiement isolé

## Notifications
- Firebase Cloud Messaging (push)
- Provider SMS local (Africa's Talking ou agrégateur camerounais)

## Hébergement
- VPS (DigitalOcean, Hetzner) au départ
- Nginx + Gunicorn
- Docker pour le déploiement
- Backups PostgreSQL automatiques chiffrés

## Monitoring
- Sentry (erreurs)
- ELK ou Grafana+Loki (logs)
- Bot Telegram alertes admin

---

# 13. PROMPT POUR CLAUDE CODE

Copie ce prompt dans Claude Code quand tu seras prêt :

---

Tu es un développeur senior Django/DRF. Je te donne la spécification complète de DJANGUI 2.0, une application de tontine, prêt instantané et investissement pour le Cameroun.

Crée le projet Django complet avec :

1. STRUCTURE DU PROJET :
   - Projet Django nommé "djangui"
   - Apps : accounts (User, Wallet, KYC), loans (Loan, Guarantee, Repayment), tontines (Tontine, Membership, Contribution), investments (Investment), transactions (Transaction), rewards (Tchekele, HonorBoard, Partner), notifications (Notification), admin_dashboard (PlatformAccount)

2. MODÈLES : implémente TOUS les 14 modèles avec les champs, types, contraintes, validations et index décrits dans la spécification. Utilise des UUID comme PK, DecimalField pour les montants, et des signaux post_save pour la création automatique du Wallet.

3. SERIALIZERS DRF : pour chaque modèle, avec des champs explicites (jamais __all__), des validations métier (score min pour emprunter, avaliste ≠ emprunteur, max 3 garanties actives, etc.).

4. VIEWS/VIEWSETS : pour tous les endpoints listés, avec permissions (IsAuthenticated, IsAdminUser), rate limiting, et vérification systématique que request.user == owner.

5. SERVICES MÉTIER : couche services/ dans chaque app pour la logique métier :
   - LoanService : create_loan, approve_loan, repay_loan, handle_default
   - GuaranteeService : create_guarantee, release_guarantee, seize_guarantee
   - WalletService : deposit, withdraw, block, unblock (tous avec transaction.atomic + select_for_update)
   - TontineService : create, join, contribute, payout
   - ReputationService : update_score (avec toutes les règles de gains/pertes)
   - CommissionService : distribute_commissions

6. TÂCHES CELERY : les 10 tâches planifiées (check_loan_expiry, check_loan_default, etc.) avec la configuration Celery Beat.

7. SÉCURITÉ : JWT avec rotation refresh, PIN hashé bcrypt, rate limiting, idempotency_key sur les transactions, CORS configuré.

8. URLS : routage complet avec les endpoints API versionnés (/api/v1/).

9. SETTINGS : configuration PostgreSQL, Redis, Celery, CORS, JWT, rate limiting.

10. REQUIREMENTS.TXT : toutes les dépendances.

Respecte STRICTEMENT les formules de calcul, les règles anti-fraude, et les invariants de wallet décrits dans la spec. Chaque opération financière DOIT être atomique.

---

FIN DU DOCUMENT
