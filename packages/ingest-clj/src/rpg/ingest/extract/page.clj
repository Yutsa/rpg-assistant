(ns rpg.ingest.extract.page
  "PDFBox extraction: TextPosition → Y bands, horizontal gaps, paragraph clusters."
  (:require [clojure.string :as str])
  (:import [org.apache.pdfbox.text TextPosition]))

(def ^:private line-tolerance 2.0)
(def ^:private gap-alpha 4.0)
(def ^:private gap-beta 6.0)
(def ^:private gap-min 12.0)
(def ^:private gap-median-cap 20.0)
(def ^:private paragraph-gap-alpha 1.8)
(def ^:private paragraph-gap-beta 4.0)
(def ^:private paragraph-gap-min 8.0)
(def ^:private paragraph-indent-min 8.0)

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
                      (when (> gap threshold)
                        (inc idx)))
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

(defn- vertical-gap [prev-segment next-segment]
  (- (:y0 (:bbox next-segment)) (:y1 (:bbox prev-segment))))

(defn- line-height [segment]
  (- (:y1 (:bbox segment)) (:y0 (:bbox segment))))

(defn- indent-delta [prev-segment next-segment]
  (- (:x0 (:bbox next-segment)) (:x0 (:bbox prev-segment))))

(defn- hyphenated-line-end? [text]
  (boolean (re-find #"[-\u00AD]$" (str/trimr text))))

(defn- paragraph-gap-threshold [segments]
  (let [gaps (mapv vertical-gap segments (rest segments))
        positive-gaps (vec (filter pos? gaps))
        gap-sample (if (seq positive-gaps) positive-gaps gaps)
        median-gap (or (median gap-sample) 2.0)
        median-line-height (or (median (mapv line-height segments)) 10.0)]
    (max (* paragraph-gap-alpha median-gap)
         (+ median-gap paragraph-gap-beta)
         (* median-line-height 0.4)
         paragraph-gap-min)))

(defn- paragraph-break? [prev-segment next-segment threshold]
  (cond
    (> (indent-delta prev-segment next-segment) paragraph-indent-min) true
    (hyphenated-line-end? (:text prev-segment)) false
    (> (vertical-gap prev-segment next-segment) threshold) true
    :else false))

(defn- cluster-paragraphs [segments]
  (if (empty? segments)
    []
    (let [sorted (vec (sort-by (comp :y0 :bbox) segments))
          threshold (paragraph-gap-threshold sorted)]
      (reduce
       (fn [paragraphs segment]
         (if (empty? paragraphs)
           [[segment]]
           (let [current-paragraph (peek paragraphs)
                 previous-segment (peek current-paragraph)]
             (if (paragraph-break? previous-segment segment threshold)
               (conj paragraphs [segment])
               (conj (pop paragraphs) (conj current-paragraph segment))))))
       []
       sorted))))

(defn- merge-paragraph-cluster [segments]
  (reduce merge-segments segments))

(defn- merge-segments-in-column [segments]
  (->> segments
       cluster-paragraphs
       (map merge-paragraph-cluster)
       vec))

(defn- merge-segments-by-font [segments page-width]
  (->> segments
       (group-by #(segment-column % page-width))
       (mapcat (fn [[_column segs]]
                 (->> segs
                      (sort-by (comp :y0 :bbox))
                      merge-segments-in-column)))
       (sort-by (juxt (comp :y0 :bbox) (comp :x0 :bbox)))
       vec))

(defn- segment-metadata [segment]
  (let [sig (:font-signature segment)]
    {:source "pdfbox_raw"
     :extraction "paragraph"
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

(def ^:private margin-ratio 0.08)
(def ^:private running-header-y-ratio 0.04)
(def ^:private margin-artifact-max-height 5.0)
(def ^:private running-header-max-chars 80)

(defn- strip-format-glyphs [text]
  (str/replace text #"[\p{Cf}\p{Co}\p{Cs}]" ""))

(defn- stripped-segment-text [text]
  (str/trim (strip-format-glyphs text)))

(defn- in-header-margin? [bbox height]
  (< (:y1 bbox) (* height margin-ratio)))

(defn- in-footer-margin? [bbox height]
  (> (:y0 bbox) (* height (- 1.0 margin-ratio))))

(defn- parasite-drm-email? [{:keys [text]}]
  (boolean (re-find #"(?i)\S+@\S+\.\S+" text)))

(defn- parasite-drm-order? [{:keys [text]}]
  (boolean (re-find #"\d{6}/\d+/\d+" text)))

(defn- parasite-page-number? [{:keys [text]}]
  (boolean (re-find #"(?i)PAGE\s+\d+" (stripped-segment-text text))))

(defn- parasite-running-header? [{:keys [text bbox]} height]
  (let [stripped (stripped-segment-text text)]
    (and (< (:y1 bbox) (* height running-header-y-ratio))
         (not (str/blank? stripped))
         (< (count stripped) running-header-max-chars))))

(defn- parasite-margin-artifact? [{:keys [bbox]} height]
  (and (< (- (:y1 bbox) (:y0 bbox)) margin-artifact-max-height)
       (or (in-header-margin? bbox height)
           (in-footer-margin? bbox height))))

(defn- parasite-block? [segment height]
  (or (parasite-drm-email? segment)
      (parasite-drm-order? segment)
      (parasite-page-number? segment)
      (parasite-running-header? segment height)
      (parasite-margin-artifact? segment height)))

(defn page-blocks [page-number width height text-positions]
  (let [raw-segments (->> text-positions
                          group-into-lines
                          (mapcat split-line-into-runs)
                          (keep run-segment)
                          vec)
        segments (->> (merge-segments-by-font raw-segments width)
                      (remove #(parasite-block? % height))
                      vec)
        blocks (keep-indexed segment-as-block segments)]
    {:page-number page-number
     :width width
     :height height
     :blocks (vec blocks)}))
