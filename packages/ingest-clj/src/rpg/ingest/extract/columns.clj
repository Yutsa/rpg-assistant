(ns rpg.ingest.extract.columns
  (:require [rpg.ingest.extract.typography :as typography]))

(defn column-side
  "Return :left or :right from a bbox center relative to page midpoint."
  [bbox page-width]
  (let [center (/ (+ (:x0 bbox) (:x1 bbox)) 2.0)
        midpoint (/ page-width 2.0)]
    (if (< center midpoint) :left :right)))

(defn same-column?
  "True when two bboxes overlap horizontally enough to share a column."
  [left-bbox right-bbox]
  (let [overlap (- (min (:x1 left-bbox) (:x1 right-bbox))
                   (max (:x0 left-bbox) (:x0 right-bbox)))
        narrow-width (min (- (:x1 left-bbox) (:x0 left-bbox))
                          (- (:x1 right-bbox) (:x0 right-bbox)))]
    (and (pos? overlap)
         (>= (/ overlap (max narrow-width 1.0)) 0.25))))

(defn line-side [line page-width]
  (column-side (:bbox line) page-width))

(defn position-side [text-position page-width]
  (let [center (+ (typography/position-x text-position)
                  (/ (typography/position-width text-position) 2.0))]
    (if (< center (/ page-width 2.0)) :left :right)))

(defn split-positions-by-column [text-positions page-width]
  {:left (vec (filter #(= :left (position-side % page-width)) text-positions))
   :right (vec (filter #(= :right (position-side % page-width)) text-positions))})

(defn split-lines-by-column [line-records page-width]
  {:left (vec (filter #(= :left (line-side % page-width)) line-records))
   :right (vec (filter #(= :right (line-side % page-width)) line-records))})

(defn column-major-block-order [blocks page-width]
  (vec (sort-by (fn [block]
                  (let [side (column-side (:bbox block) page-width)]
                    [(if (= side :left) 0 1)
                     (:y0 (:bbox block))
                     (:x0 (:bbox block))]))
                blocks)))

(defn assign-block-columns [blocks page-width]
  (mapv #(assoc-in % [:metadata :column] (name (column-side (:bbox %) page-width)))
        blocks))
