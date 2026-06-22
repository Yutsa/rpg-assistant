(ns rpg.ingest.extract.page
  "PDFBox extraction: TextPosition → Y bands, horizontal gaps, merge by font style."
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

(defn- round-font-size [size]
  (/ (Math/round (* size 10.0)) 10.0))

(defn- font-signature-from-position [text-position]
  {:font-size (round-font-size (position-font-size text-position))
   :bold? (position-bold? text-position)
   :italic? (position-italic? text-position)})

(defn- font-signature-from-positions [positions]
  (let [sizes (map position-font-size positions)]
    {:font-size (if (seq sizes)
                  (round-font-size (/ (reduce + sizes) (count sizes)))
                  0.0)
     :bold? (boolean (some position-bold? positions))
     :italic? (boolean (some position-italic? positions))}))

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

(defn- split-line-into-runs [line-positions]
  (if (empty? line-positions)
    []
    (let [sorted (vec (sort-by position-x line-positions))
          n (count sorted)
          gaps (mapv #(horizontal-gap (sorted %) (sorted (inc %))) (range (dec n)))
          threshold (gap-threshold gaps)
          split-at (keep-indexed
                    (fn [idx gap]
                      (let [prev (sorted idx)
                            next (sorted (inc idx))]
                        (when (or (> gap threshold)
                                  (not= (font-signature-from-position prev)
                                        (font-signature-from-position next)))
                          (inc idx))))
                    gaps)]
      (if (empty? split-at)
        [sorted]
        (let [boundaries (vec (concat [0] split-at [n]))]
          (mapv (fn [[start end]] (subvec sorted start end))
                (map vector boundaries (rest boundaries))))))))

(defn- run-text [positions]
  (->> positions (map position-text) (apply str) str/trim))

(defn- run-bbox [positions]
  {:x0 (apply min (map position-x positions))
   :y0 (apply min (map position-top positions))
   :x1 (apply max (map position-right positions))
   :y1 (apply max (map position-bottom positions))})

(defn- run-segment [positions]
  (let [text (run-text positions)]
    (when-not (str/blank? text)
      {:text text
       :bbox (run-bbox positions)
       :font-signature (font-signature-from-positions positions)
       :line-count 1})))

(defn- same-line? [bbox-a bbox-b]
  (< (Math/abs (- (:y0 bbox-a) (:y0 bbox-b))) line-tolerance))

(defn- merge-segments [current next-segment]
  (let [separator (if (same-line? (:bbox current) (:bbox next-segment)) " " "\n")]
    {:text (str (:text current) separator (:text next-segment))
     :bbox {:x0 (min (:x0 (:bbox current)) (:x0 (:bbox next-segment)))
            :y0 (min (:y0 (:bbox current)) (:y0 (:bbox next-segment)))
            :x1 (max (:x1 (:bbox current)) (:x1 (:bbox next-segment)))
            :y1 (max (:y1 (:bbox current)) (:y1 (:bbox next-segment)))}
     :font-signature (:font-signature current)
     :line-count (+ (:line-count current) (:line-count next-segment))}))

(defn- segment-x-center [segment]
  (/ (+ (:x0 (:bbox segment)) (:x1 (:bbox segment))) 2.0))

(defn- segment-column [segment page-width]
  ;; Two-column COF2 pages: gutter near mid-page (x-centers cluster left/right).
  (if (< (segment-x-center segment) (* page-width 0.48))
    :col-0
    :col-1))

(defn- can-merge-consecutive? [current next-segment]
  (and current
       (= (:font-signature current) (:font-signature next-segment))))

(defn- merge-segments-by-font-in-column [segments]
  (reduce
   (fn [acc segment]
     (if (empty? acc)
       [segment]
       (let [current (peek acc)
             prior (pop acc)]
         (if (can-merge-consecutive? current segment)
           (conj prior (merge-segments current segment))
           (conj acc segment)))))
   []
   segments))

(defn- merge-segments-by-font [segments page-width]
  (->> segments
       (group-by #(segment-column % page-width))
       (mapcat (fn [[_column segs]]
                 (->> segs
                      (sort-by (comp :y0 :bbox))
                      merge-segments-by-font-in-column)))
       (sort-by (juxt (comp :y0 :bbox) (comp :x0 :bbox)))
       vec))

(defn- segment-metadata [segment]
  (let [sig (:font-signature segment)]
    {:source "pdfbox_raw"
     :extraction "font-run"
     :line-count (:line-count segment)
     :max-font-size (:font-size sig)
     :avg-font-size (:font-size sig)
     :bold? (:bold? sig)
     :italic? (:italic? sig)}))

(defn- segment-as-block [block-index segment]
  {:block-index block-index
   :text (:text segment)
   :bbox (:bbox segment)
   :metadata (segment-metadata segment)})

(defn page-blocks [page-number width height text-positions]
  (let [raw-segments (->> text-positions
                          group-into-lines
                          (mapcat split-line-into-runs)
                          (keep run-segment)
                          vec)
        segments (merge-segments-by-font raw-segments width)
        blocks (keep-indexed segment-as-block segments)]
    {:page-number page-number
     :width width
     :height height
     :blocks (vec blocks)}))
