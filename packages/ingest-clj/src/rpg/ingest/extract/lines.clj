(ns rpg.ingest.extract.lines
  (:require [clojure.string :as str]
            [rpg.ingest.extract.columns :as columns]
            [rpg.ingest.extract.typography :as typography]))

(def default-line-tolerance 2.0)

(defn line-text [line-positions]
  (->> line-positions
       (map typography/position-text)
       (apply str)
       str/trim))

(defn line-bbox [line-positions]
  (let [left (apply min (map typography/position-x line-positions))
        top (apply min (map typography/position-top line-positions))
        right (apply max (map typography/position-right line-positions))
        bottom (apply max (map typography/position-bottom line-positions))]
    {:x0 left :y0 top :x1 right :y1 bottom}))

(defn line-height [line-positions]
  (let [heights (map typography/position-height line-positions)]
    (if (seq heights) (apply max heights) 12.0)))

(defn line-metadata [line-positions]
  (let [sizes (map typography/position-font-size line-positions)
        average-size (when (seq sizes) (/ (reduce + sizes) (count sizes)))]
    {:source "pdfbox"
     :line-count 1
     :max-font-size (when (seq sizes) (apply max sizes))
     :avg-font-size average-size
     :bold? (boolean (some typography/position-bold? line-positions))
     :italic? (boolean (some typography/position-italic? line-positions))}))

(defn build-line
  ([line-positions] (build-line line-positions nil))
  ([line-positions column-label]
   (when (seq line-positions)
     (let [text (line-text line-positions)]
       (when-not (str/blank? text)
         (let [metadata (cond-> (line-metadata line-positions)
                          column-label (assoc :column column-label))]
           {:positions line-positions
            :text text
            :bbox (line-bbox line-positions)
            :line-height (line-height line-positions)
            :metadata metadata}))))))

(defn vertical-gap [previous-line next-line]
  (- (:y0 (:bbox next-line)) (:y1 (:bbox previous-line))))

(defn aligned-left? [previous-line next-line tolerance]
  (<= (Math/abs (- (:x0 (:bbox previous-line))
                   (:x0 (:bbox next-line))))
      tolerance))

(defn can-merge-lines? [previous-line next-line]
  (let [gap (vertical-gap previous-line next-line)
        max-gap (max 8.0 (min 15.0 (* 1.2 (:line-height previous-line))))]
    (and (<= -5.0 gap max-gap)
         (aligned-left? previous-line next-line 18.0))))

(defn sort-lines-top-down [line-records]
  (vec (sort-by (fn [line] [(:y0 (:bbox line)) (:x0 (:bbox line))]) line-records)))

(defn- lines-from-positions
  ([text-positions] (lines-from-positions text-positions nil))
  ([text-positions column-label]
   (->> (typography/group-positions-into-lines text-positions default-line-tolerance)
        (map #(build-line % column-label))
        (remove nil?)
        vec)))

(defn- lines-from-band [band-positions page-width]
  (if-let [band-gutter (columns/band-two-column-gap band-positions page-width)]
    (let [{:keys [single full left right]}
          (columns/split-positions-by-gutter band-positions page-width
                                             {:x0 (:x0 band-gutter) :x1 (:x1 band-gutter)})]
      (vec (concat (lines-from-positions single "single")
                   (lines-from-positions full "full")
                   (lines-from-positions left "left")
                   (lines-from-positions right "right"))))
    (lines-from-positions band-positions "single")))

(defn collect-lines
  ([text-positions page-width] (collect-lines text-positions page-width nil))
  ([text-positions page-width _gutter]
   (->> (group-by #(typography/line-key % default-line-tolerance) text-positions)
        (sort-by key)
        (mapcat (fn [[_ band-positions]] (lines-from-band band-positions page-width)))
        sort-lines-top-down)))
