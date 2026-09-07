# Pokémon Jaune NJ046 — Français 2.0.12

Ce patch s'applique directement à la ROM chinoise originale **Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes**. Aucune traduction intermédiaire n'est nécessaire pour jouer.

## Application

1. Vérifier la ROM chinoise : **2 097 168 octets**, SHA-256 `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed`.
2. Appliquer `Pokemon_Jaune_NJ046_FR_v2.0.12.ips` à une copie de cette ROM avec un outil IPS.
3. Vérifier le résultat : SHA-256 `efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e`.

Ne pas utiliser la traduction anglaise de 2015, une ROM déjà traduite ou Pokémon Jaune sur Game Boy. Le nom du fichier ne garantit pas son identité. Le format IPS ne vérifie pas automatiquement la ROM source.

La 2.0.12 change la base de distribution du patch. La ROM obtenue est strictement identique à la 2.0.11 : mêmes textes, graphismes, routines et correction musicale. Le mapper reste 163. Aucun nouveau parcours complet ni test matériel n'est revendiqué pour ce changement de conditionnement.

Le compilateur vérifie la reconstruction, les 1 916 pointeurs, les limites dynamiques, le mapper et l'aller-retour IPS depuis la ROM chinoise. `SHA256SUMS` donne l'empreinte du patch, pas celle de la ROM source. Aucune ROM complète n'est distribuée.
