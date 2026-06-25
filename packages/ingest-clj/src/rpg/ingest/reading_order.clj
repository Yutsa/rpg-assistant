(ns rpg.ingest.reading-order
  "Passe 1 : ordre de lecture colonne-majeur (gauche haut→bas, droite haut→bas).")

(defn block-x-center
  [{:keys [bbox]}]
  (/ (+ (:x0 bbox) (:x1 bbox)) 2.0))

(defn column-side
  "`:left` ou `:right` selon le centre horizontal du bloc."
  [block page-width]
  (if (< (block-x-center block) (/ page-width 2.0))
    :left
    :right))

(defn column-side-index
  [block page-width]
  (if (= :left (column-side block page-width)) 0 1))

(defn column-major-sort-key
  "Tri : page → colonne (gauche=0) → y0 → x0 — aligné `reading_order.py`."
  [page-number page-width block]
  [page-number
   (column-side-index block page-width)
   (get-in block [:bbox :y0])
   (get-in block [:bbox :x0])])

(defn sort-blocks-column-major
  [blocks page-width]
  (vec (sort-by #(column-major-sort-key 0 page-width %) blocks)))

(defn reindex-blocks
  "Réattribue :block-index 0..n dans l'ordre de la liste."
  [blocks]
  (vec (map-indexed (fn [idx block] (assoc block :block-index idx)) blocks)))

(defn normalize-page-blocks
  "Trie les blocs en colonne-majeur et ré-indexe."
  [blocks page-width]
  (-> blocks
      (sort-blocks-column-major page-width)
      reindex-blocks))

(defn normalize-page
  [page]
  (update page :blocks #(normalize-page-blocks % (:width page))))

(defn normalize-reading-order
  "Applique l'ordre de lecture colonne-majeur sur chaque page."
  [pages]
  (mapv normalize-page pages))

(defn column-major-ordered?
  "Vérifie qu'une liste de blocs respecte l'ordre colonne-majeur."
  [blocks page-width]
  (let [indexed (map-indexed vector blocks)]
    (every?
     (fn [[idx block]]
       (if (zero? idx)
         true
         (let [prev (nth blocks (dec idx))
               prev-key (column-major-sort-key 0 page-width prev)
               cur-key (column-major-sort-key 0 page-width block)]
           (neg? (compare prev-key cur-key)))))
     indexed)))
