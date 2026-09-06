# Corrections de fidélité à la ROM chinoise

## Résultat

La version française a été rapprochée du texte de la ROM chinoise
`Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes`, sans reprendre les
ajouts ou réécritures les plus éloignés de la traduction anglaise.

- Les 970 dialogues principaux ont été relus à partir de leur source chinoise
  directe. Les alignements heuristiques par simple offset contenant, trop
  ambigus, ont été exclus de la source de vérité.
- Les 970 entrées françaises principales possèdent maintenant une traduction
  chinoise contrôlée et une adaptation française éditoriale explicite.
- 85 emplacements de dialogue chinois ont été restaurés :
  - 80 avaient été supprimés ou rendus inaccessibles dans la version anglaise ;
  - 4 réponses du Pont Pépite pointaient vers de mauvais textes ;
  - le message d'obtention de l'Anti-Para avait été confondu avec celui du
    Réveil dans la ROM anglaise et possède de nouveau son propre texte.
- Les caméos et références aux créateurs ont été rétablis, notamment Kameiyu
  (scénariste), Xiaohong (graphiste), Wei Cunfu (programmeur), BOSS, Beibei et
  les références à l'équipe de développement de Nanjing.
- L'inventaire final compte 17 dialogues de caméo ou de mention des créateurs,
  dont deux pour Beibei (`D0064` et `D0632`).
- La table exhaustive compte 1 055 dialogues : 970 sources alignées avec une
  confiance `high` et 85 restaurations reliées à leur `source directe`.
- Le rafraîchissement final confirme 80 pointeurs supprimés de l'anglais
  restaurés sur 80, zéro réplique encore absente de l'anglais et du français,
  85 restaurations et 17 caméos. Les 12 dérivés dépendant du français sont
  reproductibles octet par octet avec `--check`.
- HZK16 n'étant pas présent lors de ce rafraîchissement, aucune nouvelle
  extraction bitmap n'est revendiquée : les dérivés ont été recalculés depuis
  les tables Unicode immuables (`derived_refresh_without_hzk_reextraction`).

Les corrections couvrent aussi plusieurs divergences majeures : les devises
courtes de Jessie et James remplacées en anglais par de longs discours, la
dissolution temporaire de la Team Rocket, le défi de Giovanni dans le repaire,
la remise du Pokédex par le professeur Chen, la récompense d'Ondine et les
répliques finales liées à Mewtwo. Les noms officiels français de la série sont
conservés : Sacha, Régis, Jessie, James, Miaouss, Team Rocket, les Champions
d'Arène et les noms français des Pokémon. Les particularités propres au
bootleg chinois restent présentes, dont Hoenn, Johto, Nanjing, Kameiyu et les
caméos.

La récompense de Pierre est désormais `CT35 reçue !`. Le numéro est confirmé
à la fois par le dialogue chinois et par la table exécutable de la ROM : CT34
correspond à Onde de Choc, CT35 à Armure. L'ancien libellé CT34 ne décrivait
donc pas l'objet réellement remis.

## Adaptation en français naturel

Une seconde relecture éditoriale a porté sur l'ensemble des 970 dialogues
principaux contrôlés. Elle conserve les informations et le ton de
la source chinoise, mais retire les calques, les phrases nominales
télégraphiques et les formulations qui ressemblaient à des messages système.

- Les 970 dialogues principaux ont désormais une adaptation française relue.
- Les 85 dialogues restaurés ont reçu la même relecture éditoriale, soit les
  1 055 dialogues de la table exhaustive.
- Les passages déjà naturels ont été conservés ou retouchés au minimum afin
  d'éviter une réécriture arbitraire.
- Les scènes importantes de Chen, Pierre, Giovanni, M. Fuji, Ondine,
  Major Bob, Jessie et James ont été reprises en priorité.
- Les caméos de Beibei, Kameiyu, Xiaohong, Wei Cunfu et BOSS ont reçu le même
  traitement éditorial sans perdre leur identité chinoise.
- Les noms officiels français de Pokémon restent prioritaires, ainsi que
  Sacha, Régis, Jessie, James, Miaouss, la Team Rocket et les Champions
  d'Arène.
- La hiérarchie éditoriale est explicite : dialogue officiel de Pokémon Jaune
  français lorsque la scène correspond, dialogue officiel commun à Rouge,
  Bleu et Jaune ensuite, adaptation naturelle du chinois dans le style des
  jeux français sinon, puis anime français en dernier recours seulement.
- Le troisième lot éditorial ajoute 39 adaptations : il reprend notamment le
  retour d'Olga et la réouverture de la Ligue, le Parc Safari, les conseils de
  Pierre, la stratégie d'Ondine, la Team Rocket et plusieurs répliques de
  Carmin sur Mer. Ces changements proviennent tous d'alignements chinois par
  table de pointeurs à confiance élevée.
- Le quatrième lot ajoute 47 adaptations issues des mêmes alignements fiables.
  Il couvre notamment Régis, le Major Bob, Erika, Koga, la Team Rocket, la
  Sylphe SARL, les fossiles du Mont Sélénite et l'approche de la Ligue, tout en
  conservant les particularités de Nanjing présentes dans la ROM chinoise.
- Le cinquième lot ajoute 23 adaptations. Il affine notamment les conseils sur
  les types et la CS05 Flash, le Carapuce de l'Agent Jenny, Koga et le Badge
  Âme, la prise de la Sylphe SARL, plusieurs sbires Rocket et les derniers
  Dresseurs avant la Ligue.
- Le sixième lot ajoute 35 adaptations. Il rend plus spontanés les dialogues
  de Dresseurs et de sbires, précise plusieurs répliques de la Tour Pokémon et
  de la Sylphe SARL, et conserve explicitement Hoenn, la Team Rocket ainsi que
  les termes officiels français.
- Le septième lot ajoute 25 adaptations. Il allège plusieurs formulations
  encore télégraphiques, restitue les deux intervenants de quatre échanges de
  l'Arène de Jadielle et développe les remerciements du Président de la Sylphe
  SARL à partir du dialogue chinois complet.
- Le huitième lot ajoute 34 adaptations. Il restaure notamment une question
  omise sur les Pokémon du joueur, remplace des formulations nominales par du
  français parlé et affine des répliques de Dresseurs entre la Route 1,
  l'Océane, la Tour Pokémon, Parmanie et Cramois'Île.
- Le neuvième lot traite toutes les apparitions de Jessie, James et Miaouss
  selon une hiérarchie de sources explicite. Lorsqu'une scène correspond à
  Pokémon Jaune sur Game Boy, la formulation officielle française du jeu est
  prioritaire (Mont Sélénite, Repaire Rocket, Tour Pokémon et Sylphe SARL).
  Comme le jeu Game Boy ne récite pas la devise complète, les 61 segments de
  devise présents dans cette ROM adaptent la devise française de l'anime.
  Les éléments propres au bootleg chinois restent intacts : Team Nanjing,
  Kameiyu, changement de Boss et caméos de l'équipe de développement.
- Le dixième lot ajoute 29 adaptations. Lorsque le passage chinois reprend une
  scène de la première génération, il privilégie le texte français officiel de
  Pokémon Jaune ou le dialogue commun aux versions Rouge, Bleue et Jaune :
  professeur Chen, Lavanville, Scope Sylphe, Parc Safari, CS03 Surf, CS04 Force
  et Dojo de Safrania. Les formulations officielles ne sont reprises que si
  elles restent compatibles avec le sens propre à cette ROM chinoise.
- Le onzième lot ajoute 23 adaptations consacrées aux deux séquences de la
  Ligue. Il reprend les voix officielles françaises de Rouge, Bleu et Jaune :
  le parler d'Olga (« Je zuis », « Conzeil », « glaze »), le registre musclé
  d'Aldo, le ton d'Agatha, Peter, Régis et le professeur Chen. Les passages
  officiels qui contredisent le chinois ne sont pas copiés : le déroulement,
  les conclusions de combat et la seconde visite restent ceux du bootleg.
- Le douzième lot ajoute 43 adaptations : récompense de Mew, intervention de
  l'arbitre, messages d'obtention d'objets, Centre Pokémon et Boutique. Les
  noms d'objets et les tournures de service viennent en priorité des textes
  français officiels de Pokémon Jaune et des dialogues communs à Rouge, Bleu
  et Jaune. Les limitations propres au bootleg chinois restent explicites :
  combats indisponibles et machine de Troc en panne. L'anime français n'est
  utilisé qu'en dernier recours lorsqu'aucune réplique de jeu ne correspond.
- Le treizième lot ajoute 20 adaptations à Jadielle, Argenta et Lavanville.
  Dix scènes communes reprennent en priorité les formulations françaises
  officielles de la première génération : Arène fermée de Jadielle, Musée et
  conseils d'Argenta, spectres et cimetière de Lavanville, ainsi que la
  relation entre un Pokémon et son Dresseur. Les dix autres restent adaptées
  directement du chinois. Les textes officiels ne sont employés que lorsque
  la scène correspond ; l'anime demeure le dernier recours.
- Le quatorzième lot ajoute 24 adaptations parmi les conseils, les services
  et les messages système. Il conserve explicitement Hoenn, reformule le
  Conseil des 4, les huit Badges et le défi de Kameiyu, puis harmonise le PC,
  les menus, l'obtention de Carapuce et Coupe avec le style des jeux français.
  La sieste proposée par la mère de Sacha et l'accueil de la Boutique reprennent
  les dialogues officiels communs à la première génération ; les 22 autres
  textes restent adaptés directement de la source chinoise.
- Le quinzième lot ajoute 31 adaptations du début de l'aventure jusqu'aux
  routes proches de Carmin sur Mer. Les dialogues du professeur Chen, de
  Régis chez Léo et du maître de Coupe reprennent en priorité la voix des
  textes français officiels communs à Rouge, Bleu et Jaune, sans ajouter les
  phrases absentes du chinois. Le passage chez Léo restaure notamment son
  statut de collectionneur célèbre, l'enrichissement du Pokédex et son rôle
  dans la création du stockage PC. Les autres répliques donnent aux Scouts,
  Marins, fillettes et Dresseurs un ton plus spontané, tout en conservant
  Hoenn, le Major Bob et les détails propres au bootleg chinois.
- Le seizième lot ajoute 19 adaptations à Céladopole, dans la Tour Pokémon et
  dans le Repaire Rocket. Huit scènes s'appuient directement sur le
  désassemblage de Pokémon Jaune français
  `Narishma-gb/pokeyellow-fr` (révision
  `0c4b7313be40c0fc7676695c018e8ff8edab9866`) : l'homme devant l'Arène,
  la victoire annoncée d'Erika, les Pokémon Insecte ou Feu, la mère
  d'Osselait, l'entrée du Repaire, le Scope Sylphe et la cachette derrière
  l'affiche. Le texte officiel n'est repris que si la scène et le sens chinois
  correspondent. Deux anciennes substitutions Rocket sans correspondance ont
  ainsi été retirées. Le contrôle ultérieur des pointeurs actifs confirme les
  répliques chinoises réelles : `JAMES : T'as pas honte ?` à `0x03BEE1` et
  `JAMES : Tu vas voir !` à `0x03C33F`.
- Le dix-septième lot ajoute 12 adaptations dans la Tour Pokémon, la Sylphe
  SARL et sur les routes de Parmanie. Trois scènes correspondantes reprennent
  en priorité la voix de Pokémon Jaune français : la Team Rocket qui contrôle
  la Sylphe SARL, la belle prise du pêcheur et le « T'es trop mignon ! » de la
  Beauté. Les neuf autres répliques restent fondées sur le chinois et gagnent
  un français plus spontané, notamment « Quel casse-pieds ! », « Je te plais
  pas ? » et « C'est le destin ! On se revoit ! ». Les lignes anglaises qui
  décrivent une autre scène ne sont pas utilisées.
- Le dix-huitième lot ajoute 20 adaptations entre Parmanie, le Dojo de
  Safrania, les Îles Écume, Cramois'Île et la route de la Ligue. Il restitue
  notamment la Dent d'Or perdue au Parc Safari, le numéro deux du dojo, le
  Pokémon légendaire évoqué aux Îles Écume et plusieurs provocations absentes
  ou très différentes en anglais. Les termes officiels français viennent de
  Pokémon Jaune, mais aucune réplique officielle n'est déclarée comme source
  lorsqu'elle appartient à une autre scène ; l'anime n'a pas été nécessaire
  pour ce lot.
- Le dix-neuvième lot ajoute 16 adaptations. Deux scènes correspondantes
  reprennent en priorité la voix de Pokémon Jaune français : Régis chez le
  professeur Chen et le guide de l'Arène de Cramois'Île (« Salut ! Graine de
  champion! »). Les détails restent ceux du chinois : Régis explique qu'il a
  rappliqué pour un Pokémon et le guide n'ajoute pas le conseil sur les
  Pokémon Eau absent de cette ROM. Les quatorze autres répliques sont
  adaptées directement du chinois ; l'anime n'a pas été nécessaire.
- Le vingtième lot ajoute 21 adaptations. Le don de Bulbizarre s'appuie sur
  la réplique correspondante de Pokémon Jaune français, tandis que la rumeur
  du tunnel des Taupiqueur reprend le dialogue officiel commun à la première
  génération. Les dix-neuf autres textes sont adaptés directement du chinois,
  notamment l'état de siège, le Conseil des 4, l'Océane, le Mont Sélénite et
  plusieurs provocations de Dresseurs. Une formule célèbre sur les progrès de
  la technologie n'a volontairement pas été attribuée au dialogue de Bourg
  Palette : l'emplacement correspond ici à une autre scène. L'anime n'a pas
  été nécessaire pour ce lot.
- Le vingt-et-unième lot ajoute 35 adaptations. Trois dons de Pokémon propres
  à Pokémon Jaune reprennent les formulations françaises correspondantes et
  dix-huit messages ou scènes communs à la première génération emploient la
  terminologie officielle : Pokédex, Carte, Badges, CT, CS, fossiles et
  Pokémon offerts. Les quatorze autres textes restent adaptés directement du
  chinois, notamment le caméo de Kameiyu chez Nanjing Tech et celui de Xiao
  Li. L'anime n'a pas été nécessaire pour ce lot.
- Le vingt-deuxième lot ajoute 56 nouvelles adaptations et corrige une entrée
  déjà naturalisée dont l'ancienne table avait accolé deux sources voisines.
  La scène de l'Agent Jenny avec Carapuce reprend en priorité la voix de
  Pokémon Jaune français tout en conservant les faits du dialogue chinois ;
  les autres répliques sont adaptées directement du chinois. Ce lot rétablit
  aussi un message « Anti-Para reçu ! » distinct de « Réveil reçu ! », alors
  que la ROM anglaise mutualisait les deux objets. L'anime n'a pas été
  nécessaire pour ce lot.
- Le vingt-troisième lot ajoute 126 adaptations parmi les dialogues encore
  trop littéraux. Il complète notamment les voix des Dresseurs, des Champions,
  de la Team Rocket et des créateurs de Nanjing, tout en conservant les noms
  français officiels de la série et les particularités du bootleg chinois.
- Le vingt-quatrième lot relit les 157 derniers dialogues principaux hors des
  lots précédents et achève la couverture éditoriale des 970 entrées. Quarante-
  deux scènes principales reprennent une formulation de Pokémon Jaune français
  réellement correspondante, 136 emploient une formulation officielle commune
  à Rouge, Bleu et Jaune, et trois seuls segments principaux recourent à la
  devise française de l'anime. Les 85 restaurations sont toutes adaptées ; cinq
  suivent Pokémon Jaune et 58 segments de devise suivent l'anime. Une passe de
  concision éditoriale sur 137 dialogues principaux et trois restaurations
  permet le repacking sans troncature, tout en gardant le sens chinois.

La table exhaustive privilégie désormais, pour chaque dialogue principal, la
source chinoise directement atteinte par le même emplacement de pointeur que
la ROM anglaise. Un ancien rapprochement par simple offset contenant pouvait
associer un dialogue voisin : ce faux rattachement a été supprimé, notamment
pour James, Kicklee (`0x03D9DD`) et Morgane (`0x03DCAA`).

La table `french_naturalization_overrides.json` est appliquée après la table
de fidélité chinoise. Elle constitue la couche éditoriale finale, tandis que
`chinese_fidelity_dialogue_overrides.json` conserve la traduction contrôlée
de référence. Trois sous-tables rendent la provenance française vérifiable :
`french_official_yellow_dialogue_overrides.json` pour Pokémon Jaune,
`french_official_gen1_shared_dialogue_overrides.json` pour les dialogues
communs à Rouge, Bleu et Jaune, et `french_anime_motto_main_overrides.json`
pour les segments de devise du script principal.

## Caméo de Beibei

Le nom chinois `蓓蓓` est romanisé `BEIBEI`. Ses deux répliques sont présentes :

- `BEIBEI : Tu es vraiment formidable !`
- `BEIBEI : Je sais tout des jeux vidéo ! Cet Évoli est pour toi !`

## Qualité du découpage

Les changements de page historiques ont été conservés lorsque le sens du
dialogue était inchangé, puis les nouveaux textes ont été redistribués en
fonction de leur contenu.

- 967 dialogues de terrain et 2 518 pages de dialogue analysés ; avec les
  trois dialogues d'introduction, le validateur compte 2 530 bulles.
- 0 mot coupé entre deux lignes ou deux pages.
- 0 limite de page fortement problématique.
- 0 modification du sens pendant la redistribution des bulles.
- 0 texte fixe tronqué pendant la reconstruction.

## Validation technique

- 1 819 textes ordinaires et 85 dialogues restaurés ont été replacés dans leurs
  banques PRG.
- 0 échec d'allocation, conflit de pointeur, chevauchement incompatible ou
  différence lors de la reconstruction exacte des banques.
- 51 octets restent libres dans la paire PRG 6 (plus grand bloc : 11) et 135
  dans la paire PRG 7 (un bloc de 135). Les planchers 40/4 et 128/128 sont
  respectés. Le rapport de budget démontre pourquoi un bloc contigu supérieur
  à 11 octets est impossible dans la paire 6 avec ces données.
- Les 85 pointeurs restaurés ciblent tous la charge utile française attendue.
- Le manifeste de pointeurs v2 vérifie la complétude contre l'inventaire
  canonique : 1 912 références attendues et présentes, dont les 85
  restaurations. Retirer simultanément une ligne et ajuster un résumé ne peut
  donc plus produire un faux `PASS`.
- Le core normal post-release exécute 399 tests sur 50 modules avec `OK`, sans
  échec ni saut. Il inclut les régressions dédiées à
  l'adaptation française, au caméo de Beibei, à la priorité Pokémon
  Jaune/anime, à la provenance chinoise directe des dialogues repointés, à la
  complétude des pointeurs et aux preuves de runtime. Le journal terminal a le
  SHA-256 `09a254e66c044545…`.
- Le patch IPS et les deux patchs BPS réappliqués à leur base exacte
  reproduisent la ROM finale. Lunar IPS 1.03 x64 et Floating IPS v198 donnent
  trois sorties sur trois identiques octet par octet à la cible ; la preuve a
  le SHA-256 `3f53aace4f07fbed…`. Le double build de release est déterministe.
- Le builder final verrouille avant construction les SHA-256 de `script.py`
  (`e870f481…`), `traduction_base.csv` (`a4932263…`), du CSV des dépassements
  (`561ff1e5…`), de la naturalisation principale (`923a9d3b…`), de la couche
  de fidélité chinoise (`0761b3f1…`) et de la naturalisation des restaurations
  (`5cbb41c9…`).
- Le contrat du mapper 163, les vecteurs, la police française et les
  graphismes de titre/menu sont validés statiquement.
- Les 159 descriptions du Pokédex, leurs pointeurs et leurs terminateurs sont
  exacts dans la ROM compilée.
- L'audit des accents ne signale plus aucune occurrence certaine,
  contextuelle ou ambiguë.
- La suite Mesen normale compte 45/45 étapes `PASS` en Dendy, NTSC et PAL ;
  son manifeste a le SHA-256 `c75fc00b3ed9d4f3…` et porte explicitement
  `Bootstrap completion gate: False`. Le bootstrap `947d8221…` est conservé
  comme historique transitoire de pré-promotion uniquement.
  Le diagnostic Route 1/Jadielle est également `PASS` dans les trois régions ;
  il ne constitue toutefois pas une campagne complète : sa portée est
  `route1_viridian_alignment_only`, `parcel_route_done=false` et aucun
  dialogue n'y est attesté.
- Le diagnostic de RAM non initialisée reste
  `inherited_source_engine_quirk_unresolved` et
  `harmlessness_not_proven` : l'héritage de la routine est prouvé, pas son
  innocuité ni l'absence d'un déclencheur lié à la traduction.
- Le test Mesen de sauvegarde corrompue porte sur une fixture contrôlée d'un
  seul octet relatif `$0050` en Dendy, NTSC et PAL. Il ne remplace ni un
  fuzzing de sauvegarde ni une campagne complète avec reprise à chaque jalon.
- Le matériel mapper 163 physique reste explicitement `NON TESTÉ`.

## Fichiers de référence

- Corrections sémantiques :
  `tools/data/chinese_fidelity_dialogue_overrides.json`
- Adaptation française finale :
  `tools/data/french_naturalization_overrides.json`
- Vingt-troisième lot éditorial :
  `tools/data/french_naturalization_batch23_overrides.json`
- Vingt-quatrième lot éditorial :
  `tools/data/french_naturalization_batch24_overrides.json`
- Passe de concision nécessaire au stockage :
  `tools/data/french_storage_compact_dialogue_overrides.json` et
  `tools/data/french_storage_compact_restoration_overrides.json`
- Dialogues adaptés de Pokémon Jaune FR :
  `tools/data/french_official_yellow_dialogue_overrides.json`
- Dialogues officiels communs aux versions françaises R/B/J :
  `tools/data/french_official_gen1_shared_dialogue_overrides.json`
- Segments adaptés de la devise française de l'anime :
  `tools/data/french_anime_motto_main_overrides.json`
- Naturalisation des dialogues restaurés :
  `tools/data/french_restoration_naturalization_overrides.json`
- Restaurations et caméos :
  `tools/chinese_dialogue_restorations.py`
- Audit de pagination :
  `build/release-2026-08-09-final-v2/audits/dialogue_page_quality.json`
- Validation des lignes :
  `build/release-2026-08-09-final-v2/audits/dialogue_layout_validation.json`
- Audit des accents :
  `build/release-2026-08-09-final-v2/audits/french_accents.json`
- Budget des banques de texte :
  `build/release-2026-08-09-final-v2/audits/text_bank_budget.json`
- Manifeste des 1 912 références de pointeurs :
  `build/release-2026-08-09-final-v2/audits/pointer_manifest.json`
- Liste extraite des caméos :
  `build/chinese-english-fidelity/extraction/creator_cameo_dialogues.csv`

## Livrables

- ROM finale : `Pokemon_Jaune_FR_repacked_title.nes`
- Patch BPS conseillé : `Pokemon_Jaune_FR_repacked_title_from_chinese.bps`
- Patch BPS alternatif : `Pokemon_Jaune_FR_repacked_title_from_english.bps`
- Patch IPS de compatibilité : `Pokemon_Jaune_FR_repacked_title.ips`
- Bases exclusives : ROM chinoise NJ046 `450d40c0…` pour le premier BPS,
  `Pokemon Yellow English 9-23-2015.nes` `d5c308b5…` pour le second et
  `yellow.nes` `69520103…` pour l'IPS.
- SHA-256 de la ROM :
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`
- SHA-256 du BPS chinois :
  `0a1988e744d7ef4dbf2c172b34973015b8777a0ce498a3b165b59a9825ed1d22`
- SHA-256 du BPS anglais :
  `01d1c0cd27d361cfa7fb91623348d63613a14a2dc1ed344bb92c1ca2b6f7f9f7`
- SHA-256 de l'IPS :
  `912d9feaf7278f1cf0d139e4805360ad6d2232b68f98f9f9ac8e7e9bca9e5c29`
- Manifeste de release : `build/release-2026-08-09-final-v2/release_manifest.json`
