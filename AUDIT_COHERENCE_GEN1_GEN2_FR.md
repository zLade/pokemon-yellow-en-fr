# Audit de cohérence française — générations 1 et 2

## Résultat dans la remise actuelle `1fefecbf`

Les constats de cet audit, traités initialement le 28 juillet 2026, restent
verrouillés dans la release finale du 9 août 2026 :

- ROM : `Pokemon_Jaune_FR_repacked_title.nes`
- SHA-256 ROM :
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`
- IPS : `Pokemon_Jaune_FR_repacked_title.ips`
- SHA-256 IPS :
  `912d9feaf7278f1cf0d139e4805360ad6d2232b68f98f9f9ac8e7e9bca9e5c29`
- CSV : `traduction_base.csv`
- SHA-256 CSV :
  `a4932263753587b744cf3cc614f884c8754e95fec5b486f88c951adf242be803`
- source : `script.py`
- SHA-256 source :
  `e870f48105bd570d8323bf0c9358b95dbe5e59e6557214196a547cfedcb56180`

Les **39 corrections certaines** recensées ci-dessous ont été appliquées,
ainsi que l'**harmonisation terminologique** de `0x033BFE`. Il ne reste donc
aucun des 40 points de cet audit à reporter dans la source actuelle. Le test
`tools/test_coherence_corrections.py` verrouille toujours les textes corrigés
et leurs layouts.

Les huit descriptions étendues #152 à #159 sont maintenant toutes déclarées
en `pokedex_13x4`, compilées sur quatre lignes de 13 caractères au maximum et
validées sans césure de mot. Les quatre descriptions qui restaient à nettoyer
après la remise précédente — Lugia, Ho-Oh, Kyogre et Rayquaza — sont propres
dans `1fefecbf`.

Les tableaux historiques sont conservés sans réécriture afin de documenter le
problème constaté et le texte qui a ensuite été appliqué. La colonne
« Proposition exacte » décrit le résultat conservé dans `1fefecbf`, et non
une tâche encore en attente.

La release antérieure `1a5c689c…` est désormais elle aussi historique. La ROM
`80310612e2b2fd1ebbf673027e555828e1c85ecc62e87920348f5c98db4c901b`
et son IPS
`7e32b9dc8b56d06705be268a2f18c5397d686469d24627ecd764e44ba8435252`
constituent une remise encore antérieure. Ils restent des preuves historiques de
l'application initiale des corrections Gen 1/2, mais ne désignent plus les
artefacts actifs. La remise intermédiaire `42a0d940` est elle aussi historique.

## Périmètre du snapshot historique audité

Ce rapport portait sur la traduction française présente dans le snapshot
suivant, désormais archivé sous `build/archive/pre-complete-5b479227/`. Les
noms de fichiers ci-dessous sont ceux employés au moment de l'audit ; leurs
homonymes à la racine désignent aujourd'hui la remise `1fefecbf` :

- ROM : `Pokemon_Jaune_FR_repacked_title.nes`
- SHA-256 ROM : `5b479227c614428226a1d2a201435734fad6afed7d9e0a38c6b9857f2ad5f3ac`
- CSV : `traduction_base.csv`
- SHA-256 CSV : `71c1d9231fd3c3ea7438256b31ccc5daa7e914111f95c9af7b1feab4a0c2df70`
- Inventaire des frontières de dialogues : `tools/data/dialogue_boundary_inventory.json`
- SHA-256 inventaire : `30e3d6439d65abc128d76b47f1463c4324971dbc3d17f3d90908a3ee6cec5f91`
- Source historique : `script.py`
- SHA-256 source : `526e5a638968dd7c50c4c30b6268acda429d4e9e59fbfd2ebab1fe20d2d316b0`

Le bilan distingue :

1. la conformité des appellations françaises historiques ;
2. la fidélité contextuelle par rapport aux dialogues anglais présents dans la ROM ;
3. la qualité grammaticale des formulations françaises ;
4. la mise en page automatique et les collages déjà présents dans la traduction héritée.

Sur ce snapshot historique, **39 enregistrements uniques présentaient une
erreur certaine**. Un quarantième enregistrement contenait une terminologie
compréhensible, mais différente de la formulation française historique
recommandée. Ce constat initial ne décrit plus l'état de la remise
`1fefecbf`.

## Méthode

L'audit a suivi les étapes suivantes :

1. inventaire des 1 836 entrées de `traduction_base.csv`, avec comparaison des champs `source_en` et `fr_text` ;
2. comparaison systématique des tables de noms Pokémon, Dresseurs/classes, lieux, objets et attaques avec des décompilations reproductibles des ROM françaises historiques ;
3. contrôle manuel des dialogues où la version française omet une information, ajoute une information absente de l'anglais ou change le sens ;
4. contrôle des constructions françaises manifestement incomplètes ou incorrectes ;
5. nouvelle validation du reflow 17/19 caractères et audit heuristique des collages.

Les deux références externes sont épinglées à un commit précis :

- [Pokémon Rouge/Bleu français — `einstein95/pokered-fr` au commit `7ddc547`](https://github.com/einstein95/pokered-fr/tree/7ddc547e22e4c84f3e492a3c04a92c26f7f2e877)
- [Pokémon Cristal français — `gb-mobile/pokecrystal-mobile-fra` au commit `98fef35`](https://github.com/gb-mobile/pokecrystal-mobile-fra/tree/98fef35c02d28cd8f42d789aab2dfa4d5814ab16)

Ces dépôts ne constituent pas une documentation éditoriale de Nintendo : ils reproduisent toutefois les données textuelles des ROM françaises historiques et permettent une comparaison exacte et reproductible.

## Éléments cohérents

### Pokémon

La table principale couvre correctement les **151 Pokémon de Kanto** :

- 124 noms réellement traduits ;
- 27 noms identiques en anglais et en français ;
- aucune divergence constatée dans la table maîtresse.

Les substitutions `Nidoran=` et `Nidoran>` pour les symboles de sexe, ainsi que `oe` à la place de la ligature `œ`, sont des contraintes de charset acceptables et non des erreurs de traduction.

### Dresseurs et classes

Les noms vérifiés sont cohérents avec les générations 1 et 2 : Régis, Pierre, Ondine, Major Bob, Erika, Koga, Morgane, Auguste, Giovanni, Olga, Aldo, Agatha, Peter, Jessie et James.

Les classes vérifiées sont également cohérentes, notamment : Clément, Dresseur JR, Jongleur, Caïd Rocket, Jumelles, Pokéfan, Canon, Médium, Scout, Kinésiste, Fillette, Écolier, Sbire Rocket, Scientifique, Montagnard, Nageur, Nageuse, Gentleman, Crache-Feu, Marin, Topdresseur, Loubard, Intello, Gamin, Prof, Kimono, Exorciste, Pêcheur, Rocker, Ornithologue, Motard, Karatéka, Prof. Chen, Pokémaniac, Pillard, Skieuse et Surfer.

`Lugia2009` et `Ninja` sont des appellations personnalisées ou des caméos du projet ; elles ne prétendent pas remplacer une classe canonique et ne sont donc pas signalées comme erreurs.

### Lieux et badges

Les lieux principaux vérifiés sont cohérents : Bourg Palette, Jadielle, Forêt de Jade, Argenta, Mont Sélénite, Azuria, Lavanville, Safrania, Céladopole, Carmin sur Mer, Parmanie, Cramois'Île, Route Victoire et Plateau Indigo.

`Grotte` est bien l'appellation française historique employée dans Rouge/Bleu pour Rock Tunnel ; ce n'est pas un oubli de traduction.

Les huit Badges sont corrects : Roche, Cascade, Foudre, Prisme, Âme, Marais, Volcan et Terre.

### Attaques, objets abrégés et faux positifs

Les formes historiques suivantes sont intentionnelles et correctes : `Rafale Psy`, `Psyko`, `Bulles d'O`, `Météores`, `Dracosouffle`, `Ouragan`, `Écras'Face`, `Poing de Feu`, `Lance-Flamme`, `Vol-Vie`, `Bomb-Beurk`, `Cru-Aile` et `Aile d'Acier`.

Les attaques postérieures à la génération 2 et la capacité personnalisée `Brise Glacée` sont hors du référentiel strict Rouge/Bleu/Cristal ; elles ne sont pas classées comme erreurs. Les fragments sans pointeur tels que `Fou.`, `Bomb`, `Mas.`, `Tomb`, `Corn`, `Halo`, `Queu` et `Bise` ne sont pas non plus des noms complets à corriger.

Les abréviations très courtes comme `SprBall`, `HyprBall`, `MastrBal`, `BonbRare`, `PierrFeu`, `PierrEau`, `PierrFdr` et `PierrLun` sont des compromis de largeur, pas des confusions de nomenclature.

L'audit heuristique a remonté 11 suspects, dont zéro de niveau fort. Après inspection, ils sont tous faux positifs :

- `Dracosouffle` et `autrefois` ne contiennent pas de collage ;
- les trois occurrences de `Aaaah` sont des cris volontaires ;
- les doubles lettres de `inoffensif`, `Siffl'Herbe`, `Dracosouffle`, `affrontons`, `difficiles` et `différents` sont correctes.

## Huit Pokémon bonus

Les huit espèces bonus sont présentes avec leur nom français exact, qui est identique à leur nom international :

| Génération | Pokémon | Offset |
|---|---|---:|
| 2 | Raikou | `0x0364B3` |
| 2 | Entei | `0x0364BA` |
| 2 | Suicune | `0x0364C0` |
| 2 | Lugia | `0x0364C8` |
| 2 | Ho-Oh | `0x0364CE` |
| 3 | Kyogre | `0x0364D4` |
| 3 | Groudon | `0x0364DB` |
| 3 | Rayquaza | `0x0364E3` |

Le bonus se compose donc de **5 Pokémon de génération 2 et 3 Pokémon de génération 3**, et non de huit Pokémon de génération 2.

## Reflow et collages du snapshot historique

La validation de mise en page du snapshot historique donnait :

- résultat : **PASS** ;
- 512 enregistrements avec layout ;
- 814 frontières fautives corrigées ;
- 29 espaces légitimes restaurés ;
- 34 césures artificielles retirées ;
- 1 952 lignes physiques ;
- 1 089 bulles de dialogue ;
- aucune erreur de validation.

Le reflow n'a introduit **aucun** des collages observés. Les 14 enregistrements concernés contenaient déjà leur collage ou leur ponctuation fusionnée dans le texte français hérité, avant le nouveau découpage :

`0x033A48`, `0x033D67`, `0x034739`, `0x0387F3`, `0x0389B4`, `0x038B03`, `0x038BBC`, `0x038EFE`, `0x03A821`, `0x03C21F`, `0x03C370`, `0x03CA26`, `0x03E8A0` et `0x03F27B`.

Sur le snapshot historique figé, les 14 collages ciblés avaient disparu. Cela
ne signifiait pas encore que le sens de chaque enregistrement était correct :
à `0x0389B4`, le collage `decarte` avait été réparé, mais la réplique restait
infidèle à l'anglais et figurait donc dans la liste ci-dessous. Cette réplique
avait été corrigée dès `80310612` et reste verrouillée dans `1fefecbf`.

## Corrections certaines relevées puis appliquées

Les 39 lignes suivantes sont uniques. Elles restaient à corriger dans le
snapshot historique `5b479227`; leur proposition exacte a depuis été appliquée
dès `80310612`, conservée dans `1fefecbf`, puis découpée par le système de
reflow.

### Nomenclature et continuité

| Offset | Ligne source | Problème | Proposition exacte |
|---:|---:|---|---|
| `0x0317B9` | 2394 | `HelixFosil` devient l'abréviation non canonique `Fos.Nautile`. Le nom d'objet français est `Nautile`. | `Nautile` |
| `0x031BAB` | 1954 | `Oak's Parcel` est traduit `Colis du Prof` au lieu du nom d'objet historique. | `000Colis Chen` |
| `0x032301` | 2011 | La cible de chasse, Magikarp/Magicarpe, est omise. | `Il rase l'eau pour chasser un Magicarpe.` |
| `0x034A49` | 3001 | Message d'obtention du `Colis du Prof`. | `Colis Chen obtenu !` |
| `0x034A6A` | 3004 | Message d'obtention du `Fossile Nautile`, alors que l'objet français s'appelle `Nautile`. | `Nautile obtenu !` |
| `0x0364F0` | 1819 | Ordre anglais `Max Potion` conservé. Le nom français est `Potion Max`. | `Util. Potion Max !` |
| `0x03A127` | 655 | `Foret de Jade` sans graphie française correcte. | `Je retourne en Forêt de Jade.` |
| `0x03B329` | 873 | Cubone est traduit `Ossatueur` au lieu d'`Osselait`. | `Les gens paient cher les crânes d'Osselait.` |
| `0x03B34F` | 875 | La mère de Cubone devient la mère d'Ossatueur. | `J'ai vu la mère d'Osselait mourir en fuyant la Team Rocket !` |
| `0x03B516` | 897 | Cubone devient Ossatueur ; la traduction ajoute également `Je serai Champion !`, absent de la source. | `Ton Pokédex, ça va ? Je viens de capturer un Osselait ! Bon, je dois filer : j'ai beaucoup à faire. À plus !` |
| `0x03C21F` | 1039 | L'âme est celle de la mère d'Osselait, pas de la mère d'Ossatueur. | `Le fantôme était l'âme tourmentée de la mère d'Osselait ! Apaisée, elle est partie dans l'au-delà.` |
| `0x03C370` | 1050 | Même confusion Cubone/Osselait dans le dialogue de Fuji. | `Fuji : Hein ? Tu es venu me sauver ? Merci. Je suis venu apaiser l'âme de la mère d'Osselait. Je crois que son esprit repose en paix. Je dois te remercier. Suis-moi chez moi.` |

À `0x03C1EA`, `Ossatueur` est en revanche correct : le Scope Sylphe identifie bien le fantôme de Marowak.

### Fidélité contextuelle

`0x03B516` cumule nomenclature et fidélité contextuelle ; il est déjà compté dans les 12 lignes précédentes et n'est pas compté une seconde fois.

| Offset | Ligne source | Problème | Proposition exacte |
|---:|---:|---|---|
| `0x035638` | 1769 | La notion d'entraînement équilibré est omise. | `Entraîne tes Pokémon au même rythme.` |
| `0x035780` | 1780 | `Évoli évolue en 3 Pokémon` laisse entendre trois évolutions simultanées. | `Évoli peut évoluer en l'un de trois Pokémon.` |
| `0x0365FE` | 1841 | La source recommande de laisser les Pokémon se reposer ; la traduction change cela en conseil abstrait de gentillesse. | `Sacha, si tu pousses trop tes Pokémon, ils finiront par ne plus t'aimer. Tu devrais faire une pause !` |
| `0x0386A2` | 332 | `Ash, come over here` devient `Sacha choisis-en un`. | `Chen : Mais je... Bon, d'accord. Ce Pokémon est à toi. J'allais t'en donner un de toute façon. Sacha, viens ici !` |
| `0x0389B4` | 357 | Le refus de prêter la Carte par la sœur de Régis est remplacé par `Sacha, pas besoin de carte`. | `Sacha, désolé, mais je n'ai pas besoin de toi ! Je sais : j'emprunterai une Carte à ma soeur et je lui dirai de ne pas t'en prêter ! Hahaha !` |
| `0x03900E` | 448 | Ajout inventé de `Tes Pokémon t'adoreront !`. | `Tu sembles très doué comme Dresseur ! Va tester ta force à l'Arène d'Azuria !` |
| `0x0395E5` | 499 | Le laboratoire n'étudie pas seulement les fossiles : il cherche à ressusciter les Pokémon fossilisés. | `Alors celui-ci est à moi ! À Cramois'Île, un laboratoire étudie comment ressusciter les Pokémon fossilisés !` |
| `0x0396E6` | 510 | La question `A brat beat us?` devient seulement l'insulte `Sale gosse !`. | `Jessie : Un morveux nous a battus ?` |
| `0x0397E8` | 524 | Le conseil d'utiliser des Pokémon Plante disparaît. | `Hé, Champion ! Ondine est une experte des Pokémon Eau. Électrocute-les ou utilise des Pokémon Plante !` |
| `0x0398D1` | 2256 | Ondine ne pose plus la question `What's yours?`. | `Ondine : Les Dresseurs pros ont chacun leur stratégie. La mienne, c'est l'offensive totale ! Et la tienne ?` |
| `0x03D12B` | 1203 | La traduction tronquée omet que les CT ont été achetées. | `J'utilise des CT que j'ai achetées !` |

### Grammaire et construction

| Offset | Ligne source | Problème | Proposition exacte |
|---:|---:|---|---|
| `0x033436` | 2272 | `Le Conseil des 4 est après` est un calque incorrect. | `Le Conseil des 4 vient ensuite !` |
| `0x03365E` | 1558 | Construction maladroite et accents manquants dans la déclaration d'Aldo. | `Je suis Aldo du Conseil des 4 ! Grâce à un entraînement rigoureux, humains et Pokémon deviennent plus forts ! Sacha, nous allons t'écraser par notre puissance !` |
| `0x033715` | 1565 | `Les Pokémon c'est le combat` est incorrect. | `Les Pokémon sont faits pour combattre !` |
| `0x0338F4` | 1579 | `Mes dragons battus !` est un fragment sans verbe. | `Je n'arrive pas à croire que mes dragons aient perdu !` |
| `0x03675E` | 1855 | La formulation historique attribuait maladroitement l'amusement aux Pokémon. | `J'aime trouver des surnoms à mes Pokémon !` |
| `0x03A504` | 696 | `J'ai le mal !` omet `de mer`. | `Beurk ! J'ai le mal de mer !` |
| `0x03D10F` | 1202 | Articles et espace interrogatif manquants. | `Tu utilises des CT ?` |
| `0x03D31C` | 1226 | `les techniques sommeil` est incorrect. | `J'aime les techniques de poison et de sommeil.` |
| `0x03D341` | 1227 | Complément manquant dans `J'ai rejoint pour devenir ninja`. | `J'ai rejoint cette Arène pour devenir ninja !` |
| `0x03DBE1` | 1355 | Temps et articulation incorrects dans `mais je montre mes pouvoirs`. | `J'ai eu la vision de ton arrivée ! Je n'aime pas combattre, mais je vais te montrer mes pouvoirs !` |
| `0x03E1BB` | 1441 | `Éteins avec Eau` est une construction incomplète. | `Hé, Champion ! Auguste est un pro des Pokémon Feu ! Refroidis ses ardeurs avec des attaques Eau !` |
| `0x03E259` | 1444 | Deux propositions juxtaposées sans articulation. | `Je vais gagner : j'ai beaucoup étudié !` |
| `0x03E777` | 3210 | `MEW donne naissance` emploie le présent alors que le journal rapporte un événement passé. | `MEW a donné naissance à un petit. Nous l'avons baptisé MEWTWO.` |
| `0x03EAB4` | 1525 | Accord verbal et participial incorrect : `Tu nous a bien embetes`. | `Jessie : Halte, morveux ! On ne peut pas laisser la Team Rocket perdre ainsi ! James : Tu nous as bien embêtés, mais la Team Rocket ne sera jamais vaincue ! Miaouss : Miaouss ! On va te montrer qui commande !` |
| `0x03EC46` | 1531 | `J'arrive pas croire` est incomplet. | `James : Je n'arrive pas à y croire ! La Team Rocket battue par ce morveux ! Jessie : Tu as peut-être gagné cette fois, mais nous reviendrons ! Miaouss : Miaouss ! Tu n'as pas fini d'entendre parler de nous !` |
| `0x03F5A3` | 305 | Accents, accord de la locutrice et coordination manquent. | `Vieil homme : Aïe ! Fille : Désolée, mon grand-père s'est blessé au dos et ne peut plus bouger.` |

## Terminologie historique recommandée puis appliquée

Cette ligne n'était pas comptée parmi les 39 erreurs certaines, car le texte
historique restait compréhensible. La recommandation a néanmoins été appliquée
dès `80310612` et reste présente dans `1fefecbf` :

| Offset | Ligne source | Texte dans `5b479227` | Texte conservé dans `1fefecbf` |
|---:|---:|---|---|
| `0x033BFE` | 1602 | `Temple de la Gloire Pokémon` | `Félicitations Sacha ! Voici l'étage des célébrités Pokémon ! Les Champions de la Ligue et leurs Pokémon y sont consacrés. Bravo : toi et tes Pokémon êtes célèbres !` |

Dans Rouge/Bleu français, les données historiques utilisent `CÉLÉBRITÉ`, `CÉLÉBRITÉS` et la formulation `Cet étage est réservé aux célébrités Pokémon`. `Temple de la Gloire` est donc une adaptation libre, pas l'appellation historique.

## Conclusion

La nomenclature de base du projet est solide : les 151 Pokémon de Kanto, les huit espèces bonus, les principaux personnages, classes, lieux, Badges et attaques Gen 1/2 sont correctement identifiés.

Le snapshot historique `5b479227` ne pouvait pas encore être qualifié de
traduction française entièrement cohérente. Dans la remise actuelle
`1fefecbf` :

- les **39 corrections certaines** sont appliquées ;
- l'**harmonisation terminologique** est appliquée ;
- les corrections Gen 1/2 restent verrouillées par les tests de régression ;
- les **8 descriptions étendues** sont propres, compilées et sans césure ;
- le reflow est techniquement valide et n'est pas la cause des collages
  hérités ;
- les 14 collages ciblés et les erreurs de sens consignées ici sont corrigés.

La cohérence demandée par le périmètre de cet audit Gen 1/2 est donc traitée.
Cette conclusion ne prétend pas remplacer un parcours humain exhaustif de
toutes les branches optionnelles du jeu.
