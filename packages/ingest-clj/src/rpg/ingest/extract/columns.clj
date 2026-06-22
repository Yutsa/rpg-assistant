(ns rpg.ingest.extract.columns
  (:require [rpg.ingest.extract.typography :as typography]))

(def ^:private min-gutter-width-ratio 0.04)
(def ^:private min-gutter-width-pt 15.0)
(def ^:private min-lines-per-side 2)
(def ^:private min-column-line-width 60.0)
(def ^:private min-band-side-width 40.0)
(def ^:private min-band-side-positions 3)
(def ^:private full-width-ratio 0.55)
(def ^:private left-cluster-ratio 0.42)
(def ^:private right-cluster-ratio 0.58)

(defn- bbox-center-x [bbox]
  (/ (+ (:x0 bbox) (:x1 bbox)) 2.0))

(defn- bbox-width [bbox]
  (- (:x1 bbox) (:x0 bbox)))

(defn- record-bbox [record]
  (:bbox record))

(defn spans-midpoint?
  "True when a bbox crosses the page vertical midline."
  [bbox page-width]
  (let [midpoint (/ page-width 2.0)]
    (and (< (:x0 bbox) midpoint)
         (> (:x1 bbox) midpoint))))

(defn full-width-record?
  "True for lines/blocks that should stay intact (centered titles, banners, etc.)."
  [record page-width]
  (let [bbox (record-bbox record)
        width (bbox-width bbox)]
    (or (>= width (* page-width full-width-ratio))
        (spans-midpoint? bbox page-width))))

(defn- position-center-x [text-position]
  (+ (typography/position-x text-position)
     (/ (typography/position-width text-position) 2.0)))

(defn- position-right [text-position]
  (+ (typography/position-x text-position)
     (typography/position-width text-position)))

(defn- position-spans-midpoint? [text-position page-width]
  (let [midpoint (/ page-width 2.0)
        x0 (typography/position-x text-position)
        x1 (position-right text-position)]
    (and (< x0 midpoint)
         (> x1 midpoint))))

(defn- min-gutter-width [page-width]
  (max min-gutter-width-pt (* page-width min-gutter-width-ratio)))

(defn- largest-position-gap [positions]
  (when (>= (count positions) 2)
    (let [sorted (sort-by typography/position-x positions)]
      (loop [remaining (rest sorted)
             previous (first sorted)
             best {:width 0 :split-index 0}]
        (if (empty? remaining)
          best
          (let [current (first remaining)
                gap (- (typography/position-x current)
                       (position-right previous))
                index (- (count sorted) (count remaining))
                next-best (if (> gap (:width best))
                            {:width gap :split-index index}
                            best)]
            (recur (rest remaining) current next-best)))))))

(defn band-two-column-gap [positions page-width]
  (let [candidates (remove #(position-spans-midpoint? % page-width) positions)
        gap (largest-position-gap candidates)]
    (when (and gap (pos? (:width gap)) (>= (:width gap) (min-gutter-width page-width)))
      (let [sorted (sort-by typography/position-x candidates)
            split-index (:split-index gap)
            left (subvec (vec sorted) 0 split-index)
            right (subvec (vec sorted) split-index)]
        (when (and (seq left) (seq right))
          (let [left-width (- (position-right (last left)) (typography/position-x (first left)))
                right-width (- (position-right (last right)) (typography/position-x (first right)))]
            (when (and (>= left-width min-band-side-width)
                       (>= right-width min-band-side-width)
                       (>= (count left) min-band-side-positions)
                       (>= (count right) min-band-side-positions))
              {:x0 (position-right (last left))
               :x1 (typography/position-x (first right))
               :width (:width gap)})))))))

(defn- position-bands [text-positions line-tolerance]
  (->> text-positions
       (group-by #(typography/line-key % line-tolerance))
       (map (fn [[_ positions]] positions))))

(defn page-gutter-from-positions [text-positions page-width line-tolerance]
  (let [band-gutters (keep #(band-two-column-gap % page-width) (position-bands text-positions line-tolerance))
        two-column-bands (count band-gutters)]
    (when (>= two-column-bands min-lines-per-side)
      (let [x0 (/ (reduce + (map :x0 band-gutters)) (count band-gutters))
            x1 (/ (reduce + (map :x1 band-gutters)) (count band-gutters))]
        {:x0 x0 :x1 x1}))))

(defn- bucket-for-position [position page-width gutter]
  (cond
    (not gutter) :single
    (position-spans-midpoint? position page-width) :full
    (< (position-center-x position) (:x0 gutter)) :left
    (> (position-center-x position) (:x1 gutter)) :right
    :else (if (< (position-center-x position) (/ page-width 2.0)) :left :right)))

(defn split-positions-by-gutter [text-positions page-width gutter]
  (reduce (fn [acc position]
            (update acc (bucket-for-position position page-width gutter) conj position))
          {:single [] :full [] :left [] :right []}
          text-positions))

(defn- cluster-side-lines [line-records page-width side]
  (let [left-threshold (* page-width left-cluster-ratio)
        right-threshold (* page-width right-cluster-ratio)]
    (filter
     (fn [line]
       (let [center (bbox-center-x (record-bbox line))]
         (and (>= (bbox-width (record-bbox line)) min-column-line-width)
              (case side
                :left (< center left-threshold)
                :right (> center right-threshold)
                false))))
     line-records)))

(defn find-gutter-from-line-clusters [line-records page-width]
  (let [candidates (remove #(full-width-record? % page-width) line-records)
        left-lines (cluster-side-lines candidates page-width :left)
        right-lines (cluster-side-lines candidates page-width :right)]
    (when (and (>= (count left-lines) min-lines-per-side)
               (>= (count right-lines) min-lines-per-side))
      (let [left-edge (apply max (map :x1 (map record-bbox left-lines)))
            right-edge (apply min (map :x0 (map record-bbox right-lines)))
            gap (- right-edge left-edge)]
        (when (>= gap (min-gutter-width page-width))
          {:x0 left-edge :x1 right-edge})))))

(defn page-gutter [line-records page-width]
  (find-gutter-from-line-clusters line-records page-width))

(defn two-column-page? [line-records page-width]
  (boolean (page-gutter line-records page-width)))

(defn line-column [line page-width gutter]
  (cond
    (not gutter) :single
    (full-width-record? line page-width) :full
    (< (bbox-center-x (record-bbox line)) (:x0 gutter)) :left
    (> (bbox-center-x (record-bbox line)) (:x1 gutter)) :right
    :else (if (< (bbox-center-x (record-bbox line)) (/ page-width 2.0)) :left :right)))

(defn column-side [bbox page-width gutter]
  (cond
    (not gutter) "single"
    (full-width-record? {:bbox bbox} page-width) "full"
    (< (bbox-center-x bbox) (:x0 gutter)) "left"
    (> (bbox-center-x bbox) (:x1 gutter)) "right"
    :else (if (< (bbox-center-x bbox) (/ page-width 2.0)) "left" "right")))

(defn same-column? [left-bbox right-bbox]
  (let [overlap (- (min (:x1 left-bbox) (:x1 right-bbox))
                   (max (:x0 left-bbox) (:x0 right-bbox)))
        narrow-width (min (- (:x1 left-bbox) (:x0 left-bbox))
                          (- (:x1 right-bbox) (:x0 right-bbox)))]
    (and (pos? overlap)
         (>= (/ overlap (max narrow-width 1.0)) 0.25))))

(defn split-lines-by-column [line-records page-width gutter]
  (if gutter
    (reduce (fn [acc line]
              (update acc (line-column line page-width gutter) conj line))
            {:single [] :full [] :left [] :right []}
            line-records)
    {:single line-records :full [] :left [] :right []}))

(defn- column-sort-priority [column]
  (get {:single 0 :full 0 :left 1 :right 2} column 0))

(defn order-blocks [blocks _page-width _gutter]
  (vec
   (sort-by
    (fn [block]
      (let [column (keyword (get-in block [:metadata :column] "single"))]
        [(:y0 (:bbox block))
         (column-sort-priority column)
         (:x0 (:bbox block))]))
    blocks)))

(defn assign-block-columns [blocks page-width gutter]
  (mapv #(assoc-in % [:metadata :column] (column-side (:bbox %) page-width gutter))
        blocks))

(defn column-major-block-order [blocks page-width]
  (order-blocks blocks page-width nil))
