(ns rpg.ingest.extract.columns
  (:require [rpg.ingest.extract.typography :as typography]))

(def ^:private min-gutter-width-ratio 0.04)
(def ^:private min-gutter-width-pt 15.0)
(def ^:private min-lines-per-side 2)
(def ^:private full-width-ratio 0.55)
(def ^:private gutter-search-start-ratio 0.2)
(def ^:private gutter-search-end-ratio 0.8)

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

(defn- sample-covered? [x line-records]
  (some (fn [line]
          (let [bbox (record-bbox line)]
            (and (<= (:x0 bbox) x)
                 (>= (:x1 bbox) x))))
        line-records))

(defn- longest-uncovered-run [covered start-index end-index]
  (loop [index start-index
         best {:start start-index :end start-index :width 0}
         run-start nil]
    (if (>= index end-index)
      best
      (if (aget covered index)
        (recur (inc index)
               best
               nil)
        (let [start (or run-start index)
              width (inc (- index start))]
          (recur (inc index)
                 (if (> width (:width best))
                   {:start start :end (inc index) :width width}
                   best)
                 start))))))

(defn find-central-gutter
  "Return {:x0 :x1} for the widest empty vertical band in the page center."
  [line-records page-width]
  (let [sample-count (max 100 (int page-width))
        step (/ page-width sample-count)
        search-start (int (* page-width gutter-search-start-ratio))
        search-end (int (* page-width gutter-search-end-ratio))
        covered (boolean-array sample-count)]
    (doseq [line line-records
            sample (range search-start search-end)]
      (let [x (* sample step)
            index (min (dec sample-count) (int (/ x step)))]
        (when (sample-covered? x [line])
          (aset covered index true))))
    (let [gap (longest-uncovered-run covered search-start search-end)
          min-width (max min-gutter-width-pt (* page-width min-gutter-width-ratio))]
      (when (>= (:width gap) min-width)
        {:x0 (* (:start gap) step)
         :x1 (* (:end gap) step)}))))

(defn- lines-on-side [line-records gutter side]
  (count
   (filter
    (fn [line]
      (let [center (bbox-center-x (record-bbox line))]
        (case side
          :left (< center (:x0 gutter))
          :right (> center (:x1 gutter))
          false)))
    line-records)))

(defn two-column-page?
  "True when a central gutter exists and both sides have enough body lines."
  [line-records page-width]
  (let [candidates (remove #(full-width-record? % page-width) line-records)
        gutter (find-central-gutter candidates page-width)]
    (and gutter
         (>= (lines-on-side candidates gutter :left) min-lines-per-side)
         (>= (lines-on-side candidates gutter :right) min-lines-per-side))))

(defn line-column
  "Classify a line as :single, :full, :left or :right."
  [line page-width gutter]
  (cond
    (not gutter) :single
    (full-width-record? line page-width) :full
    (< (bbox-center-x (record-bbox line)) (:x0 gutter)) :left
    (> (bbox-center-x (record-bbox line)) (:x1 gutter)) :right
    :else (if (< (bbox-center-x (record-bbox line)) (/ page-width 2.0)) :left :right)))

(defn column-side
  "Return column label for a block bbox."
  [bbox page-width gutter]
  (cond
    (not gutter) "single"
    (full-width-record? {:bbox bbox} page-width) "full"
    (< (bbox-center-x bbox) (:x0 gutter)) "left"
    (> (bbox-center-x bbox) (:x1 gutter)) "right"
    :else (if (< (bbox-center-x bbox) (/ page-width 2.0)) "left" "right")))

(defn same-column?
  "True when two bboxes overlap horizontally enough to share a column."
  [left-bbox right-bbox]
  (let [overlap (- (min (:x1 left-bbox) (:x1 right-bbox))
                   (max (:x0 left-bbox) (:x0 right-bbox)))
        narrow-width (min (- (:x1 left-bbox) (:x0 left-bbox))
                          (- (:x1 right-bbox) (:x0 right-bbox)))]
    (and (pos? overlap)
         (>= (/ overlap (max narrow-width 1.0)) 0.25))))

(defn position-side [text-position page-width gutter]
  (let [center (+ (typography/position-x text-position)
                  (/ (typography/position-width text-position) 2.0))]
    (cond
      (not gutter) :single
      (< center (:x0 gutter)) :left
      (> center (:x1 gutter)) :right
      :else :full)))

(defn- position-center-x [text-position]
  (+ (typography/position-x text-position)
     (/ (typography/position-width text-position) 2.0)))

(defn- position-spans-midpoint? [text-position page-width]
  (let [midpoint (/ page-width 2.0)
        x0 (typography/position-x text-position)
        x1 (+ x0 (typography/position-width text-position))]
    (and (< x0 midpoint)
         (> x1 midpoint))))

(defn- column-candidate-positions [text-positions page-width]
  (filter (fn [position]
            (not (position-spans-midpoint? position page-width)))
          text-positions))

(defn- find-gutter-from-position-centers [text-positions page-width]
  (let [centers (sort (map position-center-x text-positions))
        mid-start (* page-width gutter-search-start-ratio)
        mid-end (* page-width gutter-search-end-ratio)
        min-width (max min-gutter-width-pt (* page-width min-gutter-width-ratio))]
    (loop [remaining (filter #(and (>= % mid-start) (<= % mid-end)) centers)
           best {:x0 mid-start :x1 mid-start :width 0}
           prev nil]
      (if (empty? remaining)
        (when (>= (:width best) min-width) best)
        (let [current (first remaining)
              next-best (if prev
                          (let [gap (- current prev)]
                            (if (> gap (:width best))
                              {:x0 prev :x1 current :width gap}
                              best))
                          best)]
          (recur (rest remaining) next-best current))))))

(defn- positions-on-side [text-positions gutter side]
  (count
   (filter
    (fn [position]
      (let [center (position-center-x position)]
        (case side
          :left (< center (:x0 gutter))
          :right (> center (:x1 gutter))
          false)))
    text-positions)))

(defn page-gutter-from-positions [text-positions page-width]
  (let [candidates (column-candidate-positions text-positions page-width)
        gutter (find-gutter-from-position-centers candidates page-width)]
    (when (and gutter
               (>= (positions-on-side candidates gutter :left) (* min-lines-per-side 3))
               (>= (positions-on-side candidates gutter :right) (* min-lines-per-side 3)))
      gutter)))

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

(defn page-gutter [line-records page-width]
  (when (two-column-page? line-records page-width)
    (let [candidates (remove #(full-width-record? % page-width) line-records)]
      (find-central-gutter candidates page-width))))

(defn split-lines-by-column [line-records page-width]
  (if-let [gutter (page-gutter line-records page-width)]
    (reduce (fn [acc line]
              (update acc (line-column line page-width gutter) conj line))
            {:single [] :full [] :left [] :right []}
            line-records)
    {:single line-records :full [] :left [] :right []}))

(defn- column-sort-priority [column]
  (get {:single 0 :full 0 :left 1 :right 2} column 0))

(defn order-blocks [blocks page-width gutter]
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
