# Audit chinois–anglais de NJ046

## Verdict

La ROM anglaise du 23 septembre 2015 n'est **pas une traduction fidèle
globale** de la ROM chinoise NJ046. Les scènes principales, plusieurs noms et
une partie des messages système sont proches de la source, mais l'ensemble
contient aussi :

- des reformulations et réécritures non littérales ;
- de nombreux dialogues de PNJ associés au mauvais texte anglais ;
- des descriptions du Pokédex remplacées par d'autres anecdotes ;
- des contresens dans les états de combat et les capacités ;
- des pointeurs manifestement erronés ;
- des textes chinois restés sous forme graphique dans la ROM anglaise.

La ROM anglaise peut donc servir de référence ponctuelle, mais pas de source
de vérité pour traduire NJ046.

## Périmètre et reproductibilité

ROMs contrôlées par SHA-256 :

- chinois : `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`
- anglais : `d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b`
- français restauré actuel :
  `1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b`

La police chinoise est stockée en tuiles 16×16. Les bitmaps ont été associés à
Unicode avec HZK16, puis validés par la routine de rendu 6502. Les codes pairs
et impairs utilisent deux plans distincts d'un même bloc de 64 octets.

Les fichiers Unicode issus de cette extraction sont désormais traités comme
des sources immuables et contrôlés par SHA-256. HZK16 n'étant pas disponible
lors du dernier rafraîchissement, aucune nouvelle extraction bitmap n'est
revendiquée : les tables qui dépendent du français sont reconstruites depuis
ces sources épinglées, avec la provenance explicite
`derived_refresh_without_hzk_reextraction`.

Résultat de l'extraction :

| Mesure | Résultat |
| --- | ---: |
| Blocs chinois contenant du texte graphique | 1 974 |
| Occurrences de caractères chinois | 20 832 |
| Codes de caractères distincts | 1 352 |
| Codes résolus en Unicode | 1 352 |
| Entrées anglaises inventoriées | 1 844 |
| Entrées alignées à un bloc chinois | 1 829 |
| Entrées anglaises encore graphiques | 303 |
| Entrées classées comme dialogues | 970 |
| Dialogues structurellement alignés | 961 |
| Dialogues dont l'anglais reste graphique | 113 |
| Pointeurs de répliques chinoises invalidés dans la ROM anglaise | 80 |
| Ces pointeurs restaurés dans la ROM française actuelle | 80 |
| Répliques encore absentes de l'anglais et du français actuels | 0 |
| Restaurations françaises inventoriées | 85 |
| Dialogues de caméo ou de mention des créateurs | 17 |

Les deux glyphes dont la tuile est écrasée par le code final de la banque ont
été reconstruits sans ambiguïté grâce à leurs occurrences répétées :
`法` dans `培育方法` et `赢的方法`, et `瓦` dans `沙瓦郎`, `瓦斯弹` et
`双弹瓦斯`.

## Vérification de fidélité

L'alignement principal ne repose pas sur la proximité physique des textes :
les tables de pointeurs ont été détectées indépendamment dans les deux ROMs,
puis les mêmes emplacements de pointeurs ont été comparés. Cela produit
1 840 couples, dont 1 795 ont une cible résolue. Parmi eux, 295 pointent encore
vers des graphismes dans la ROM anglaise et 1 500 sont lisibles en ASCII.

La revue comparative des 1 500 couples lisibles montre trois tendances :

1. Les introductions, boss, messages structurants et beaucoup de noms restent
   généralement reconnaissables.
2. Le Pokédex est très souvent adapté : le Pokémon reste le bon, mais le fait
   décrit n'est pas celui du chinois. Ce n'est pas une traduction littérale.
3. De grandes séries de PNJ et de dresseurs sont décalées, réordonnées ou
   remplacées par des dialogues sans rapport. Plusieurs erreurs touchent aussi
   la logique du combat.

Exemples reproductibles :

| Référence | Chinois | Sens français | Anglais présent | Diagnostic |
| --- | --- | --- | --- | --- |
| `0x03005D` | `没有效果!` | Aucun effet ! | `Missed!` | mauvais résultat de combat |
| `0x03006B` | `中剧毒了` | Gravement empoisonné | `Flinched` | mauvais état |
| `0x030163` | `比试失败了` | Combat perdu | `Won!` | sens inversé |
| `0x031033` | `岩碎` | Éclate-Roc | `Low Kick` | mauvaise capacité |
| `0x03103B` | `二段踢` | Double Pied | `Revenge` | mauvaise capacité |
| `0x0310AD` | `刀背打` | Faux-Chage | `Scratch` | mauvaise capacité |
| `0x0310B5` | `鼾声` | Ronflement | `Fake Out` | mauvaise capacité |
| `0x0310DB` | `撒娇` | Charme | `Bulk-up` | mauvaise capacité |
| `0x03834B` | `谈判小子:有两下子` | « Pas mal » | `Got Charmander!` | mauvais pointeur |
| `0x03834F` | `迷你裙:我今后就关注你吧` | « Je vais te suivre de près » | `I saw trainers from all over!` | mauvais pointeur |
| `0x038353` | `侦察员:你是第一个打败我们的` | « Tu es le premier à nous battre » | `I'm off to see Bill` | mauvais pointeur |

Les erreurs aux quatre emplacements `0x038347`, `0x03834B`, `0x03834F` et
`0x038353` confirment en particulier un groupe de redirections fautives après
un combat.

## Fichiers produits

- `build/chinese-english-fidelity/extraction/chinese_glyph_map.csv` :
  correspondance des 1 352 codes avec Unicode.
- `build/chinese-english-fidelity/extraction/chinese_records.csv` :
  les 1 974 blocs chinois, avec offsets et texte Unicode.
- `build/chinese-english-fidelity/extraction/chinese_dialogues.csv` :
  les 970 entrées classées comme dialogues et leur contrepartie anglaise.
- `build/chinese-english-fidelity/extraction/chinese_english_alignment.csv` :
  toutes les entrées du script anglais alignées.
- `build/chinese-english-fidelity/extraction/pointer_alignment.csv` :
  comparaison indépendante par emplacement de pointeur.
- `build/chinese-english-fidelity/extraction/reviewed_fidelity_issues.csv` :
  les erreurs sévères ci-dessus sous forme exploitable.
- `build/chinese-english-fidelity/extraction/summary.json` :
  statistiques, empreintes de toutes les entrées et sorties, mode de
  provenance et contrôles de complétude.
- `build/chinese-english-fidelity/extraction/dialogues_absent_from_english_and_french.csv` :
  inventaire actuel des répliques encore absentes des deux versions ; il doit
  contenir zéro ligne après restauration.
- `build/chinese-english-fidelity/extraction/dialogues_removed_from_english.csv` :
  les 80 suppressions de la ROM anglaise, conservées indépendamment de l'état
  courant de la ROM française afin que la table exhaustive reste reproductible.
- `build/chinese-english-fidelity/extraction/restored_chinese_dialogues.csv` :
  les 85 restaurations actuelles avec chinois, état anglais et français.
- `build/chinese-english-fidelity/extraction/creator_cameo_dialogues.csv` :
  les 17 dialogues de caméos, reconstruits depuis la table de relecture
  courante.
- `build/chinese-english-fidelity/extraction/reviewed_large_dialogue_divergences.csv` :
  56 divergences sémantiques majeures vérifiées.

L'extraction intégrale reproductible reste implémentée par
`tools/audit_chinese_english_fidelity.py` et requiert HZK16. Sans ce fichier,
`tools/refresh_chinese_fidelity_derivatives.py` ne refait pas l'extraction :
il contrôle les deux CSV Unicode immuables, la ROM chinoise, la ROM anglaise,
la ROM française, le script et la table exhaustive, puis republie seulement
les dérivés. Son option `--check` les reconstruit temporairement et les compare
octet par octet aux fichiers publiés.

Dans le gate final v2, ce contrôle `--check` porte sur les 12 dérivés publiés
et réussit sans différence. Il confirme ensemble le bilan 80/80/0, les 85
restaurations, les 17 caméos et la liaison à la ROM française `1fefecbf…`.
Cette réussite ne doit pas être décrite comme une nouvelle extraction HZK16 :
elle prouve la reproductibilité des dérivés français à partir de l'extraction
Unicode épinglée.

## Limites

Les 1 974 blocs incluent non seulement les dialogues, mais aussi les noms,
menus, capacités, objets, messages de combat et notices du Pokédex. Le fichier
`chinese_dialogues.csv` correspond aux 970 entrées anglaises/françaises qui
utilisent les mises en page de dialogue connues. Il ne comptait donc pas les
80 répliques source dont les pointeurs ont été supprimés par le patch anglais.
Elles figurent dans `dialogues_removed_from_english.csv` et dans
`restored_chinese_dialogues.csv` avec les cinq autres restaurations ; le
fichier d'absence actuel est vide. Neuf entrées du premier fichier ne peuvent
pas être alignées automatiquement ; tous les textes chinois restent néanmoins
intégralement extraits dans `chinese_records.csv`.

L'audit est statique : il couvre le contenu et les pointeurs de la ROM, sans
prétendre que toutes les branches ont été déclenchées dans une partie jouée.
Il suffit toutefois à réfuter la fidélité globale de la traduction anglaise
et à localiser les erreurs vérifiables.
