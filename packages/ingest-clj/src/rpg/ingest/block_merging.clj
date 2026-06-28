(ns rpg.ingest.block-merging
  "Post-extraction block merges: spread titles, meta-box bodies, layout-glyphs."
  (:require [clojure.string :as str]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.stat-blocks.core :as stat-core]
            [rpg.ingest.stat-blocks.registry]))

(def ^:private max-vertical-gap 15.0)
(def ^:private max-vertical-overlap 5.0)
(def ^:private narrow-box-x-margin 35.0)
(def ^:private narrow-box-max-vertical-gap 130.0)
(def ^:private layout-glyph-max-font 7.0)

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
  [left right & {:keys [separator]}]
  (let [sep (or separator "\n")]
    {:block-index (:block-index left)
     :text (str (str/trimr (:text left)) sep (str/triml (:text right)))
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
        after-spread (merge-spread-title-pairs after-glyphs page median-font)
        after-meta (merge-meta-box-bodies (:blocks after-spread) page median-font profile-id)]
    {:page (assoc page :blocks (ro/normalize-page-blocks (:blocks after-meta)))
     :merged-count (+ (:merged-count after-spread) (:merged-count after-meta))}))

(defn merge-fragmented-pages
  "Merge spread-title pairs and meta-box body fragments on each page."
  ([pages] (merge-fragmented-pages pages nil))
  ([pages profile-id]
   (let [results (mapv #(merge-page-blocks % profile-id) pages)
         pages' (mapv :page results)
         total (reduce + (map :merged-count results))]
     {:pages pages'
      :merged-block-count total})))
