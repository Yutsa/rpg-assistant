(ns rpg.ingest.chunks
  "Phase 3+5 : blocs narratifs → chunks 1:1 ; fiches → chunks stat_block."
  (:require [clojure.string :as str]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.stat-blocks.core :as stat-core]
            [rpg.ingest.stat-blocks.registry]
            [rpg.ingest.stat-blocks.text-utils :as tu]
            [rpg.ingest.text.reflow :as reflow])
  (:import [java.text Normalizer Normalizer$Form]))

(defn- normalize-stat-block-key [^String value]
  (let [nfd (Normalizer/normalize (.trim (.toLowerCase value)) Normalizer$Form/NFD)]
    (apply str
           (for [c (.toCharArray nfd)
                 :when (not= Character/NON_SPACING_MARK (Character/getType (int c)))]
             c))))

(defn- apply-stat-block-lookup-keys [stat-block]
  (cond-> stat-block
    (seq (:name stat-block))
    (assoc :_lookup-name (normalize-stat-block-key (:name stat-block)))
    (and (:subtitle stat-block) (seq (:subtitle stat-block)))
    (assoc :_lookup-subtitle (normalize-stat-block-key (:subtitle stat-block)))))

(defn enrich-chunk-metadata
  [metadata]
  (if-let [sb (:stat-block metadata)]
    (assoc metadata :stat-block (apply-stat-block-lookup-keys sb))
    metadata))

(defn- merge-bboxes [blocks]
  {:x0 (apply min (map #(get-in % [:bbox :x0]) blocks))
   :y0 (apply min (map #(get-in % [:bbox :y0]) blocks))
   :x1 (apply max (map #(get-in % [:bbox :x1]) blocks))
   :y1 (apply max (map #(get-in % [:bbox :y1]) blocks))})

(defn- make-chunk
  [campaign-id document-id section-id chunk-index page block]
  (let [page-num (:page-number page)
        block-id (ids/page-block-id document-id page-num (:block-index block))
        text (reflow/reflow-chunk-text (:text block))]
    {:id (ids/chunk-id document-id page-num chunk-index)
     :campaign-id campaign-id
     :document-id document-id
     :section-id section-id
     :page-start page-num
     :page-end page-num
     :text text
     :chunk-type nil
     :chunk-type-hint nil
     :source-spans [{:page page-num
                     :page-block-ids [block-id]
                     :bbox (:bbox block)}]
     :metadata {}
     :needs-rechunk false}))

(defn- make-stat-chunk
  [campaign-id document-id section-id chunk-index span profile-id]
  (let [blocks (:blocks span)
        parsed (stat-core/parse-span profile-id span)
        text (reflow/reflow-chunk-text (or (:raw-text parsed)
                                          (->> blocks (map :text) (str/join "\n\n"))))
        page-numbers (map :page-number blocks)
        page-start (apply min page-numbers)
        page-end (apply max page-numbers)
        spans-by-page (group-by :page-number blocks)
        source-spans
        (vec
         (for [page-num (sort (keys spans-by-page))
               :let [page-blocks (get spans-by-page page-num)]]
           {:page page-num
            :page-block-ids (mapv #(ids/page-block-id document-id page-num (:block-index %))
                                  page-blocks)
            :bbox (merge-bboxes page-blocks)}))]
    {:id (ids/chunk-id document-id page-start chunk-index)
     :campaign-id campaign-id
     :document-id document-id
     :section-id section-id
     :page-start page-start
     :page-end page-end
     :text text
     :chunk-type nil
     :chunk-type-hint "stat_block"
     :source-spans source-spans
     :metadata (enrich-chunk-metadata
                {:stat-block parsed
                 :game-system (:game-system parsed)
                 :stat-block-span-id (:id span)})
     :needs-rechunk false}))

(defn build-chunks-1to1
  "Create one chunk per body block listed in block-assignments (titres et fiches exclus)."
  [pages {:keys [campaign-id document-id block-assignments]}]
  (let [pages (ro/normalize-reading-order pages)
        body-blocks
        (for [page pages
              block (:blocks page)
              :let [page-num (:page-number page)
                    block-id (ids/page-block-id document-id page-num (:block-index block))
                    section-id (get block-assignments block-id)]
              :when (and section-id (not (stat-core/stat-block-block? block)))]
          {:page page :block block :section-id section-id})]
    (vec
     (map-indexed
      (fn [idx {:keys [page block section-id]}]
        (make-chunk campaign-id document-id section-id idx page block))
      body-blocks))))

(defn- stat-block-header-position [pages span-id]
  (some (fn [page]
          (some (fn [block]
                  (when (and (= span-id (get-in block [:metadata :stat-block-id]))
                             (= "header" (get-in block [:metadata :stat-block-role])))
                    [(:page-number page) (:block-index block)]))
                (:blocks page)))
        pages))

(defn- resolve-stat-block-section-id
  [pages sections header-pos default-section-id]
  (let [[page-num header-idx] header-pos
        page (first (filter #(= (:page-number %) page-num) pages))
        header-block (first (filter #(= (:block-index %) header-idx) (:blocks page)))
        header-side (ro/column-side header-block (:width page))
        preceding-text
        (->> (:blocks page)
             (filter #(and (< (:block-index %) header-idx)
                           (= header-side (ro/column-side % (:width page)))
                           (not= "header" (get-in % [:metadata :stat-block-role]))))
             (map #(tu/strip-layout-glyphs (:text %)))
             (str/join " ")
             str/lower-case)]
    (if (seq (str/trim preceding-text))
      (let [{:keys [best]} (reduce
                            (fn [acc section]
                              (if (or (> (:page-start section) page-num)
                                      (< (:page-end section) page-num))
                                acc
                                (let [title-norm (str/lower-case (tu/strip-layout-glyphs (:title section)))]
                                  (cond
                                    (and (seq title-norm) (str/includes? preceding-text title-norm))
                                    (let [score (+ (count title-norm) 10)]
                                      (if (> score (:best-score acc 0))
                                        {:best (:id section) :best-score score}
                                        acc))
                                    :else
                                    (let [words (filter #(>= (count %) 3) (str/split title-norm #"\W+"))
                                          matched (count (filter #(str/includes? preceding-text %) words))]
                                      (if (and (pos? (count words))
                                               (>= matched (min 2 (count words)))
                                               (> matched (:best-score acc 0)))
                                        {:best (:id section) :best-score matched}
                                        acc))))))
                            {}
                            sections)]
        (or best default-section-id))
      default-section-id)))

(defn- reassign-stat-block-sections
  [chunks pages sections]
  (mapv (fn [chunk]
          (if (= "stat_block" (:chunk-type-hint chunk))
            (let [span-id (:stat-block-span-id (:metadata chunk))
                  header-pos (when span-id (stat-block-header-position pages span-id))]
              (if header-pos
                (assoc chunk :section-id
                       (resolve-stat-block-section-id pages sections header-pos (:section-id chunk)))
                chunk))
            chunk))
        chunks))

(defn materialize-stat-chunks
  [pages spans profile-id {:keys [campaign-id document-id block-assignments]} start-index]
  (vec
   (map-indexed
    (fn [offset span]
      (let [header-pos (stat-block-header-position pages (:id span))
            default-section
            (when header-pos
              (let [[page-num block-idx] header-pos
                    block-id (ids/page-block-id document-id page-num block-idx)]
                (get block-assignments block-id)))
            chunk (make-stat-chunk campaign-id document-id default-section
                                   (+ start-index offset) span profile-id)]
        chunk))
    spans)))

(defn build-chunks
  "Narrative 1:1 chunks plus one stat_block chunk per span."
  [pages section-result spans profile-id {:keys [campaign-id document-id]}]
  (let [chunk-opts {:campaign-id campaign-id
                    :document-id document-id
                    :block-assignments (:block-assignments section-result)}
        narrative (build-chunks-1to1 pages chunk-opts)
        stat (materialize-stat-chunks pages spans profile-id chunk-opts (count narrative))
        combined (into narrative stat)]
    (reassign-stat-block-sections combined pages (:sections section-result))))

(defn refine-section-page-ends
  "Tighten section :page-end from assigned chunk spans."
  [sections chunks]
  (let [page-ends
        (reduce
         (fn [acc chunk]
           (if-let [sid (:section-id chunk)]
             (update acc sid (fnil max 0) (:page-end chunk))
             acc))
         {}
         chunks)]
    (vec
     (for [section sections]
       (if-let [pe (get page-ends (:id section))]
         (assoc section :page-end pe)
         section)))))

(defn chunk-block-signature
  "Set of page_block ids referenced by a chunk."
  [chunk]
  (set (mapcat :page-block-ids (:source-spans chunk))))

(defn chunk-uniqueness-stats
  [chunks]
  (if (empty? chunks)
    {:chunk-unique-block-signature-count 0
     :duplicate-chunk-count 0
     :chunk-unique-block-signature-ratio 1.0}
    (let [signatures (map chunk-block-signature chunks)
          unique-count (count (set signatures))]
      {:chunk-unique-block-signature-count unique-count
       :duplicate-chunk-count (- (count chunks) unique-count)
       :chunk-unique-block-signature-ratio (/ unique-count (count chunks))})))
