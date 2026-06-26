(ns rpg.ingest.chunks
  "Phase 3 : blocs contenu → chunks 1:1 via block-assignments (passe 2)."
  (:require [rpg.ingest.ids :as ids]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.text.reflow :as reflow]))

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

(defn build-chunks-1to1
  "Create one chunk per body block listed in block-assignments (titres exclus)."
  [pages {:keys [campaign-id document-id block-assignments]}]
  (let [pages (ro/normalize-reading-order pages)
        body-blocks
        (for [page pages
              block (:blocks page)
              :let [page-num (:page-number page)
                    block-id (ids/page-block-id document-id page-num (:block-index block))
                    section-id (get block-assignments block-id)]
              :when section-id]
          {:page page :block block :section-id section-id})]
    (vec
     (map-indexed
      (fn [idx {:keys [page block section-id]}]
        (make-chunk campaign-id document-id section-id idx page block))
      body-blocks))))

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
