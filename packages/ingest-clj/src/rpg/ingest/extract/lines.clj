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

(defn build-line [line-positions]
  (when (seq line-positions)
    (let [text (line-text line-positions)]
      (when-not (str/blank? text)
        {:positions line-positions
         :text text
         :bbox (line-bbox line-positions)
         :line-height (line-height line-positions)
         :metadata (line-metadata line-positions)}))))

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

(defn- lines-from-positions [text-positions]
  (->> (typography/group-positions-into-lines text-positions default-line-tolerance)
       (map build-line)
       (remove nil?)
       vec))

(defn collect-lines [text-positions page-width]
  (let [gutter (columns/page-gutter-from-positions text-positions page-width)
        {:keys [single full left right]} (columns/split-positions-by-gutter text-positions page-width gutter)
        lines (if (seq single)
                (lines-from-positions single)
                (vec (concat (lines-from-positions full)
                             (lines-from-positions left)
                             (lines-from-positions right))))]
    (sort-lines-top-down lines)))
