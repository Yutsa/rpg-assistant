(ns rpg.ingest.block-merging
  "Post-extraction block merges: spread titles, meta-box bodies, layout-glyphs."
  (:require [clojure.string :as str]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.stat-blocks.core :as stat-core]
            [rpg.ingest.stat-blocks.registry]))

(def ^:private max-vertical-gap 15.0)
(def ^:private max-vertical-overlap 5.0)
(def ^:private min-column-overlap 0.25)
(def ^:private wrap-top-align-tolerance 20.0)
(def ^:private wrap-min-extend-past 10.0)
(def ^:private wrap-vertical-jump 20.0)
(def ^:private style-font-size-tolerance 1.5)
(def ^:private column-center-ratio 0.5)
(def ^:private narrow-box-x-margin 35.0)
(def ^:private narrow-box-max-vertical-gap 130.0)
(def ^:private layout-glyph-max-font 7.0)
(def ^:private hyphen-chars #"\-‐‑–—")
(def ^:private hyphen-end-re (re-pattern (str "[" hyphen-chars "]\\s*$")))
(def ^:private strong-end-re #"[.!?»][\'\")\]]*\\s*$")
(def ^:private incomplete-wrap-end-re
  #"(?i)\b(?:Les|La|Le|Des|Un|Une|Du|De|l'|d'|n'|s'|m'|t'|c'|j')\s*$")
(def ^:private new-unit-start-re #"^[\s«•\-–—*]+|[A-Z][A-Z\s]{3,}")

(defn- merge-bboxes [blocks]
  {:x0 (apply min (map #(get-in % [:bbox :x0]) blocks))
   :y0 (apply min (map #(get-in % [:bbox :y0]) blocks))
   :x1 (apply max (map #(get-in % [:bbox :x1]) blocks))
   :y1 (apply max (map #(get-in % [:bbox :y1]) blocks))})

(defn- merge-metadata [left right]
  (let [lm (:metadata left)
        rm (:metadata right)]
    (cond-> {:source (or (:source lm) "pdfbox_raw")
             :extraction (or (:extraction lm) "paragraph")
             :line-count (+ (or (:line-count lm) 0) (or (:line-count rm) 0))
             :max-font-size (max (or (:max-font-size lm) 0.0)
                                 (or (:max-font-size rm) 0.0))
             :avg-font-size (/ (+ (or (:avg-font-size lm) 0.0)
                                 (or (:avg-font-size rm) 0.0))
                               2.0)
             :is-bold (or (:is-bold lm) (:is-bold rm))
             :italic? (or (:italic? lm) (:italic? rm))}
      (or (:list-item-start lm) (:list-item-start rm))
      (assoc :list-item-start true)
      (or (:spread-title lm) (:spread-title rm))
      (assoc :spread-title true)
      (or (:meta-box-body lm) (:meta-box-body rm))
      (assoc :meta-box-body true))))

(defn- merge-two-blocks
  [left right & {:keys [separator hyphenation?]}]
  (let [sep (cond
              hyphenation? ""
              separator separator
              :else " ")
        merged-text (if hyphenation?
                      (let [left' (str/replace (str/trimr (:text left)) hyphen-end-re "")]
                        (str left' (str/triml (:text right))))
                      (str (str/trimr (:text left)) sep (str/triml (:text right))))]
    {:block-index (:block-index left)
     :text merged-text
     :bbox (merge-bboxes [left right])
     :metadata (merge-metadata left right)}))

(defn- layout-glyph-parasite? [block]
  (let [text (str/trim (:text block))
        font (or (:max-font-size (:metadata block)) 0.0)]
    (and (pos? (count text))
         (<= font layout-glyph-max-font)
         (<= (count text) 6)
         (boolean (re-matches #"^W+$" text)))))

(defn- filter-layout-glyphs [blocks]
  (vec (remove layout-glyph-parasite? blocks)))

(defn- block-starts-left? [block page-width]
  (< (get-in block [:bbox :x0]) (* page-width column-center-ratio)))

(defn- block-starts-right? [block page-width]
  (>= (get-in block [:bbox :x0]) (* page-width column-center-ratio)))

(defn- visually-adjacent? [left right]
  (let [gap (- (get-in right [:bbox :y0]) (get-in left [:bbox :y1]))
        min-overlap (- (min (get-in left [:bbox :y1]) (get-in right [:bbox :y1]))
                       (max (get-in left [:bbox :y0]) (get-in right [:bbox :y0])))]
    (and (>= min-overlap 0)
         (<= (- gap) max-vertical-overlap)
         (<= gap max-vertical-gap))))

(defn- shares-text-line? [left right]
  (let [overlap (- (min (get-in left [:bbox :y1]) (get-in right [:bbox :y1]))
                   (max (get-in left [:bbox :y0]) (get-in right [:bbox :y0])))]
    (> overlap 0)))

(defn- same-column? [left right]
  (>= (ro/horizontal-overlap-ratio left right) min-column-overlap))

(defn- continues-sentence? [text]
  (let [stripped (str/triml text)]
    (and (seq stripped)
         (Character/isLowerCase (.codePointAt stripped 0)))))

(defn- ends-with-hyphen? [text]
  (boolean (re-find hyphen-end-re (str/trimr text))))

(defn- ends-with-strong-punctuation? [text]
  (boolean (re-find strong-end-re (str/trimr text))))

(defn- wrap-around-continues? [prev-text next-text]
  (cond
    (continues-sentence? next-text) true
    (ends-with-strong-punctuation? prev-text) false
    :else (boolean (re-find incomplete-wrap-end-re (str/trimr prev-text)))))

(defn- starts-new-unit? [text]
  (let [stripped (str/triml text)]
    (or (not (seq stripped))
        (boolean (re-matches new-unit-start-re stripped)))))

(defn- looks-like-heading? [block page-blocks block-idx profile-id page]
  (let [role (get-in block [:metadata :stat-block-role])]
    (cond
      (#{"header" "stats" "icon"} role) true
      (and profile-id page-blocks block-idx
           (stat-core/profile-false-heading? profile-id block page-blocks block-idx page)) true
      :else
      (let [text (str/trim (:text block))
            font (or (get-in block [:metadata :avg-font-size])
                     (get-in block [:metadata :max-font-size])
                     0.0)]
        (cond
          (not (seq text)) false
          (and (get-in block [:metadata :is-bold])
               (< (count text) 80)
               (>= font 12.0)) true
          (and (< (count text) 50) (= text (.toUpperCase text))) true
          :else false)))))

(defn- compatible-style? [left right page-blocks next-idx profile-id page]
  (let [lm (:metadata left)
        rm (:metadata right)]
    (if (= (:italic? lm) (:italic? rm))
      true
      (if (looks-like-heading? right page-blocks next-idx profile-id page)
        false
        (let [prev-size (or (:avg-font-size lm) (:max-font-size lm))
              next-size (or (:avg-font-size rm) (:max-font-size rm))]
          (and prev-size next-size
               (<= (Math/abs (- prev-size next-size)) style-font-size-tolerance)))))))

(defn- wrap-around-pair? [left right page-width page-blocks next-idx profile-id page]
  (and (not (and (block-starts-left? left page-width)
                 (block-starts-left? right page-width)))
       (not (and (block-starts-right? left page-width)
                 (block-starts-right? right page-width)))
       (block-starts-left? left page-width)
       (block-starts-right? right page-width)
       (compatible-style? left right page-blocks next-idx profile-id page)
       (not (ends-with-strong-punctuation? (:text left)))
       (wrap-around-continues? (:text left) (:text right))
       (not (looks-like-heading? right page-blocks next-idx profile-id page))
       (let [aligned-tops (<= (Math/abs (- (get-in left [:bbox :y0])
                                            (get-in right [:bbox :y0])))
                              wrap-top-align-tolerance)
             prev-extends (> (get-in left [:bbox :y1]) (+ (get-in right [:bbox :y1])
                                                          wrap-min-extend-past))
             beside (and aligned-tops prev-extends (shares-text-line? left right))
             bottom-to-top (< (get-in right [:bbox :y0])
                              (- (get-in left [:bbox :y0]) wrap-vertical-jump))]
         (or beside bottom-to-top))))

(defn- merge-kind [left right page-width page-blocks next-idx profile-id page]
  (cond
    (looks-like-heading? right page-blocks next-idx profile-id page) nil
    (wrap-around-pair? left right page-width page-blocks next-idx profile-id page) :line-break
    (not (continues-sentence? (:text right))) nil
    (ends-with-hyphen? (:text left))
    (if (or (shares-text-line? left right) (visually-adjacent? left right))
      :hyphenation
      nil)
    (not (visually-adjacent? left right)) nil
    (not (same-column? left right)) nil
    (ends-with-strong-punctuation? (:text left)) nil
    (starts-new-unit? (:text right)) nil
    :else :line-break))

(defn- merge-fragmented-block-pairs
  [blocks page profile-id]
  (if (< (count blocks) 2)
    {:blocks blocks :merged-count 0}
    (loop [idx 0
           merged []
           merged-count 0]
      (if (>= idx (count blocks))
        {:blocks (vec merged) :merged-count merged-count}
        (let [[current next-idx merged-count']
              (loop [current (nth blocks idx)
                     next-idx (inc idx)
                     merged-count' merged-count]
                (if (>= next-idx (count blocks))
                  [current next-idx merged-count']
                  (let [kind (merge-kind current (nth blocks next-idx)
                                         (:width page) blocks next-idx profile-id page)]
                    (if kind
                      (recur (merge-two-blocks current (nth blocks next-idx)
                                               :hyphenation? (= kind :hyphenation))
                             (inc next-idx)
                             (inc merged-count'))
                      [current next-idx merged-count']))))]
          (recur next-idx (conj merged current) merged-count'))))))

(defn- merge-spread-title-pairs
  [blocks page median-font]
  (loop [remaining blocks merged [] merged-count 0]
    (if (empty? remaining)
      {:blocks merged :merged-count merged-count}
      (let [current (first remaining)
            nxt (second remaining)]
        (if (and nxt
                 (ro/is-spread-title-pair? current nxt page median-font))
          (recur (drop 2 remaining)
                 (conj merged
                       (-> (merge-two-blocks current nxt :separator " ")
                           (assoc-in [:metadata :spread-title] true)))
                 (inc merged-count))
          (recur (rest remaining) (conj merged current) merged-count))))))

(defn- in-meta-box? [block heading]
  (and (<= (get-in block [:bbox :y0]) (+ (get-in heading [:bbox :y1]) narrow-box-max-vertical-gap))
       (>= (get-in block [:bbox :x0]) (- (get-in heading [:bbox :x0]) narrow-box-x-margin))
       (<= (get-in block [:bbox :x1]) (+ (get-in heading [:bbox :x1]) narrow-box-x-margin))
       (> (get-in block [:bbox :y0]) (get-in heading [:bbox :y0]))))

(defn- stat-block-protected?
  [block page-blocks block-idx page profile-id]
  (or (stat-core/stat-block-block? block)
      (and profile-id
           (stat-core/profile-false-heading? profile-id block page-blocks block-idx page))))

(defn- meta-box-body-block?
  [block heading page median-font page-blocks block-idx profile-id]
  (and (in-meta-box? block heading)
       (not (ro/is-meta-box-heading? (:text block)))
       (not (ro/is-decorative-spread-title? block page median-font))
       (not (stat-block-protected? block page-blocks block-idx page profile-id))
       (not (and (pos? block-idx)
                 (ro/is-spread-title-pair?
                  (nth page-blocks (dec block-idx)) block page median-font)))
       (not (layout-glyph-parasite? block))))

(defn- merge-meta-box-bodies
  [blocks page median-font profile-id]
  (let [headings (vec (filter #(ro/is-meta-box-heading? (:text %)) blocks))
        absorbed (atom #{})
        replacements (atom {})]
    (doseq [heading headings]
      (let [body-blocks
            (vec
             (for [[idx block] (map-indexed vector blocks)
                   :when (and (not (contains? @absorbed (:block-index block)))
                              (not= block heading)
                              (meta-box-body-block? block heading page median-font blocks idx profile-id))]
               block))]
        (when (>= (count body-blocks) 2)
          (let [ordered (vec (sort-by (comp :y0 :bbox) body-blocks))
                merged (-> (reduce merge-two-blocks (first ordered) (rest ordered))
                           (assoc-in [:metadata :meta-box-body] true)
                           (assoc :block-index (:block-index (first ordered))))]
            (swap! absorbed into (map :block-index (rest ordered)))
            (swap! replacements assoc (:block-index (first ordered)) merged)))))
    (if (empty? @replacements)
      {:blocks blocks :merged-count 0}
      (let [result (vec
                    (for [block blocks
                          :let [idx (:block-index block)]
                          :when (not (contains? @absorbed idx))]
                      (or (get @replacements idx) block)))
            merged-count (- (count blocks) (count result))]
        {:blocks result :merged-count merged-count}))))

(defn- merge-page-blocks [page profile-id]
  (let [median-font (ro/page-median-font (:blocks page))
        after-glyphs (filter-layout-glyphs (:blocks page))
        after-fragmented (merge-fragmented-block-pairs after-glyphs page profile-id)
        after-spread (merge-spread-title-pairs (:blocks after-fragmented) page median-font)
        after-meta (merge-meta-box-bodies (:blocks after-spread) page median-font profile-id)]
    {:page (assoc page :blocks (ro/normalize-page-blocks (:blocks after-meta)))
     :merged-count (+ (:merged-count after-fragmented)
                      (:merged-count after-spread)
                      (:merged-count after-meta))}))

(defn merge-fragmented-pages
  "Merge spread-title pairs and meta-box body fragments on each page."
  ([pages] (merge-fragmented-pages pages nil))
  ([pages profile-id]
   (let [results (mapv #(merge-page-blocks % profile-id) pages)
         pages' (mapv :page results)
         total (reduce + (map :merged-count results))]
     {:pages pages'
      :merged-block-count total})))
