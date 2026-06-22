(ns rpg.ingest.extract.page
  "PDFBox extraction: TextPosition → Y bands, then horizontal gap splitting."
  (:require [clojure.string :as str])
  (:import [org.apache.pdfbox.text TextPosition]))

(def ^:private line-tolerance 2.0)
(def ^:private gap-alpha 4.0)
(def ^:private gap-beta 6.0)
(def ^:private gap-min 12.0)
(def ^:private gap-median-cap 20.0)

(defn- position-x [text-position]
  (.getXDirAdj ^TextPosition text-position))

(defn- position-y [text-position]
  (.getYDirAdj ^TextPosition text-position))

(defn- position-width [text-position]
  (.getWidthDirAdj ^TextPosition text-position))

(defn- position-height [text-position]
  (.getHeight ^TextPosition text-position))

(defn- vertical-extent [text-position]
  (let [font-size (.getFontSizeInPt ^TextPosition text-position)]
    (if (pos? font-size) font-size (position-height text-position))))

(defn- position-top [text-position]
  (- (position-y text-position) (vertical-extent text-position)))

(defn- position-bottom [text-position]
  (+ (position-y text-position) (* (vertical-extent text-position) 0.25)))

(defn- position-right [text-position]
  (+ (position-x text-position) (position-width text-position)))

(defn- position-font-size [text-position]
  (.getFontSizeInPt ^TextPosition text-position))

(defn- position-text [text-position]
  (.getUnicode ^TextPosition text-position))

(defn- position-bold? [text-position]
  (let [font (.getFont ^TextPosition text-position)
        font-name (when font (.getName font))]
    (boolean (and font-name (re-find #"(?i)bold" font-name)))))

(defn- position-italic? [text-position]
  (let [font (.getFont ^TextPosition text-position)
        font-name (when font (.getName font))]
    (boolean (and font-name (re-find #"(?i)(italic|oblique)" font-name)))))

(defn- line-key [text-position]
  (Math/round (/ (position-y text-position) line-tolerance)))

(defn- group-into-lines [text-positions]
  (->> text-positions
       (sort-by (juxt position-y position-x))
       (group-by line-key)
       (sort-by key)
       (map (fn [[_key positions]] positions))
       vec))

(defn- horizontal-gap [prev-pos next-pos]
  (- (position-x next-pos) (position-right prev-pos)))

(defn- median [values]
  (let [sorted (vec (sort values))
        n (count sorted)]
    (when (pos? n)
      (let [mid (quot n 2)]
        (if (odd? n)
          (nth sorted mid)
          (/ (+ (nth sorted (dec mid)) (nth sorted mid)) 2.0))))))

(defn- gap-threshold [gaps]
  (let [calibration (filter #(< % gap-median-cap) gaps)
        median-gap (or (median calibration) 2.0)]
    (max (* gap-alpha median-gap) (+ median-gap gap-beta) gap-min)))

(defn- split-line-by-gaps [line-positions]
  (if (<= (count line-positions) 1)
    [(vec line-positions)]
    (let [sorted (vec (sort-by position-x line-positions))
          n (count sorted)
          gaps (mapv #(horizontal-gap (sorted %) (sorted (inc %))) (range (dec n)))
          threshold (gap-threshold gaps)
          split-at (keep-indexed (fn [idx gap] (when (> gap threshold) (inc idx))) gaps)]
      (if (empty? split-at)
        [sorted]
        (let [boundaries (vec (concat [0] split-at [n]))]
          (mapv (fn [[start end]] (subvec sorted start end))
                (map vector boundaries (rest boundaries))))))))

(defn- line-runs [line-positions]
  (split-line-by-gaps line-positions))

(defn- line-text [line-positions]
  (->> line-positions (map position-text) (apply str) str/trim))

(defn- line-bbox [line-positions]
  {:x0 (apply min (map position-x line-positions))
   :y0 (apply min (map position-top line-positions))
   :x1 (apply max (map position-right line-positions))
   :y1 (apply max (map position-bottom line-positions))})

(defn- line-metadata [line-positions]
  (let [sizes (map position-font-size line-positions)
        average-size (when (seq sizes) (/ (reduce + sizes) (count sizes)))]
    {:source "pdfbox_raw"
     :extraction "line"
     :line-count 1
     :max-font-size (when (seq sizes) (apply max sizes))
     :avg-font-size average-size
     :bold? (boolean (some position-bold? line-positions))
     :italic? (boolean (some position-italic? line-positions))}))

(defn- line-as-block [block-index line-positions]
  (let [text (line-text line-positions)]
    (when-not (str/blank? text)
      {:block-index block-index
       :text text
       :bbox (line-bbox line-positions)
       :metadata (line-metadata line-positions)})))

(defn page-blocks [page-number width height text-positions]
  (let [runs (mapcat line-runs (group-into-lines text-positions))
        blocks (keep-indexed line-as-block runs)]
    {:page-number page-number
     :width width
     :height height
     :blocks (vec blocks)}))
