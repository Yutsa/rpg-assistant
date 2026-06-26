(ns rpg.ingest.reading-order
  "Passe 1 : ordre de lecture par tri spatial (x0, y0, x1).")

(def ^:private min-column-overlap 0.35)

(defn spatial-sort-key
  "Tri générique : position horizontale puis verticale."
  [block]
  [(get-in block [:bbox :x0])
   (get-in block [:bbox :y0])
   (get-in block [:bbox :x1])])

(defn sort-blocks-spatial
  [blocks]
  (vec (sort-by spatial-sort-key blocks)))

(defn reindex-blocks
  "Réattribue :block-index 0..n dans l'ordre de la liste."
  [blocks]
  (vec (map-indexed (fn [idx block] (assoc block :block-index idx)) blocks)))

(defn normalize-page-blocks
  "Trie les blocs en ordre spatial et ré-indexe."
  [blocks]
  (-> blocks sort-blocks-spatial reindex-blocks))

(defn normalize-page
  [page]
  (update page :blocks normalize-page-blocks))

(defn normalize-reading-order
  "Applique le tri spatial sur chaque page."
  [pages]
  (mapv normalize-page pages))

(defn spatial-ordered?
  "Vérifie qu'une liste de blocs respecte l'ordre (x0, y0, x1)."
  [blocks]
  (every? true?
          (map (fn [[prev cur]]
                 (neg? (compare (spatial-sort-key prev) (spatial-sort-key cur))))
               (partition 2 1 blocks))))

(defn horizontal-overlap-ratio
  "Ratio de chevauchement horizontal (plus étroit / overlap) — pour passe 2."
  [left right]
  (let [overlap (- (min (get-in left [:bbox :x1]) (get-in right [:bbox :x1]))
                   (max (get-in left [:bbox :x0]) (get-in right [:bbox :x0])))]
    (if (<= overlap 0)
      0.0
      (let [narrower (min (- (get-in left [:bbox :x1]) (get-in left [:bbox :x0]))
                          (- (get-in right [:bbox :x1]) (get-in right [:bbox :x0])))]
        (if (<= narrower 0)
          0.0
          (/ overlap narrower))))))

(defn is-in-column-band?
  "Deux blocs partagent-ils la même bande horizontale (fils de lecture parallèles)."
  ([block heading]
   (is-in-column-band? block heading min-column-overlap))
  ([block heading min-overlap]
   (>= (horizontal-overlap-ratio block heading) min-overlap)))

(defn block-x-cluster
  "Cluster x grossier (x0) pour assertions de test."
  [block]
  (get-in block [:bbox :x0]))
