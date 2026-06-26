(ns rpg.ingest.pipeline
  "Full import: extract PDFBox pages + blocks, sections, chunks → SQLite."
  (:require [clojure.string :as str]
            [next.jdbc :as jdbc]
            [rpg.ingest.chunks :as chunks]
            [rpg.ingest.coverage :as coverage]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.sections :as sections]
            [rpg.ingest.storage.db :as db]
            [rpg.ingest.storage.raw :as raw]))

(defn- page-text [blocks]
  (->> blocks (map :text) (str/join "\n\n") str/trim))

(defn- block-record [document-id page-id page-number block]
  {:id (ids/page-block-id document-id page-number (:block-index block))
   :document-id document-id
   :page-id page-id
   :page-number page-number
   :block-index (:block-index block)
   :text (:text block)
   :bbox (:bbox block)
   :metadata (:metadata block)})

(defn- page-record [document-id page coverage-ratio]
  (let [page-number (:page-number page)
        blocks (:blocks page)
        page-id (ids/page-id document-id page-number)
        text (page-text blocks)]
    {:page {:id page-id
            :document-id document-id
            :page-number page-number
            :text text
            :extraction-method "pdfbox"
            :has-text (boolean (seq text))
            :text-coverage-ratio coverage-ratio
            :width (:width page)
            :height (:height page)}
     :blocks (mapv #(block-record document-id page-id page-number %) blocks)}))

(defn- build-page-records [document-id extracted page-ratios]
  (let [per-page
        (mapv (fn [page ratio]
                (page-record document-id page ratio))
              (:pages extracted)
              page-ratios)]
    {:pages (mapv :page per-page)
     :blocks (vec (mapcat :blocks per-page))}))

(defn- page-coverage-ratios [extracted]
  (mapv (fn [page]
          (coverage/page-text-coverage-ratio
           (page-text (:blocks page))
           (:width page)
           (:height page)))
        (:pages extracted)))

(defn- run-stats
  [pdf-path page-count block-count section-count chunk-count avg-coverage uniqueness]
  (merge {:page_count page-count
          :block_count block-count
          :section_count section-count
          :chunk_count chunk-count
          :text_coverage_ratio avg-coverage
          :source_pdf_path (.getAbsolutePath (java.io.File. pdf-path))
          :extraction_method "pdfbox"}
         uniqueness))

(defn- import-result [run-id campaign-id document-id status & {:keys [stats error-message]}]
  (cond-> {:ingestion-run-id run-id
           :campaign-id campaign-id
           :document-id document-id
           :status status}
    stats (assoc :stats stats)
    error-message (assoc :error-message error-message)))

(defn- persist-extracted-data!
  [ds {:keys [run-id document-id campaign-id pdf-path content-hash pages blocks
              sections chunks reimport]}]
  (raw/upsert-document! ds document-id campaign-id
                        (.getName (java.io.File. pdf-path))
                        (count pages) content-hash)
  (raw/update-ingestion-run! ds run-id :document-id document-id)
  (when reimport
    (raw/delete-document-raw-data! ds document-id))
  (jdbc/with-transaction [tx ds]
    (raw/insert-pages! tx pages)
    (raw/insert-page-blocks! tx blocks)
    (raw/insert-sections! tx sections)
    (raw/insert-chunks! tx chunks)))

(defn- complete-import!
  [ds run-id campaign-id document-id pdf-path pages blocks sections chunks]
  (let [uniqueness (chunks/chunk-uniqueness-stats chunks)
        stats (run-stats pdf-path (count pages) (count blocks)
                         (count sections) (count chunks)
                         (coverage/document-coverage-ratio
                          (map :text-coverage-ratio pages))
                         uniqueness)]
    (raw/update-ingestion-run! ds run-id :status "completed" :stats stats :finished true)
    (import-result run-id campaign-id document-id "completed" :stats stats)))

(defn- reject-import!
  [ds run-id campaign-id document-id avg-coverage page-count threshold]
  (let [message (str "PDF rejected: insufficient text coverage ("
                     (format "%.2f" avg-coverage) " < " threshold "). "
                     "A text-based PDF is required; scanned/image-only PDFs are unsupported.")
        stats {:text_coverage_ratio avg-coverage
               :page_count page-count}]
    (raw/update-ingestion-run! ds run-id
                               :status "rejected"
                               :document-id document-id
                               :error-message message
                               :stats stats
                               :finished true)
    (import-result run-id campaign-id document-id "rejected"
                   :error-message message
                   :stats stats)))

(defn- fail-import! [ds run-id campaign-id document-id exception]
  (raw/update-ingestion-run! ds run-id
                             :status "failed"
                             :error-message (.getMessage exception)
                             :finished true)
  (import-result run-id campaign-id document-id "failed"
                 :error-message (.getMessage exception)))

(defn import-pdf!
  "Import a PDF: pages, blocks, sections and chunks. Returns result map."
  [{:keys [pdf-path campaign-id campaign-title game-system reimport db-spec
           coverage-threshold]
    :or {reimport true}}]
  (let [threshold (or coverage-threshold coverage/default-coverage-threshold)run-id (ids/new-id "run")
        content-hash (ids/hash-file pdf-path)
        document-id (ids/document-id-from-hash content-hash)
        ds (db/connect :db-spec db-spec)]
    (raw/ensure-campaign! ds campaign-id :title campaign-title :game-system game-system)
    (raw/create-ingestion-run! ds {:id run-id
                                   :campaign-id campaign-id
                                   :status "running"})
    (try
      (let [extracted (pdf/extract-document pdf-path)
            page-ratios (page-coverage-ratios extracted)
            avg-coverage (coverage/document-coverage-ratio page-ratios)]
        (if (coverage/scanned-or-unusable? page-ratios threshold)
          (reject-import! ds run-id campaign-id document-id
                          avg-coverage (count (:pages extracted)) threshold)
          (let [{:keys [pages blocks]} (build-page-records document-id extracted page-ratios)
                section-result (sections/assign-sections (:pages extracted)
                                                         {:campaign-id campaign-id
                                                          :document-id document-id})
                built-chunks (chunks/build-chunks-1to1 (:pages extracted)
                                                       {:campaign-id campaign-id
                                                        :document-id document-id
                                                        :block-assignments (:block-assignments section-result)})
                refined-sections (chunks/refine-section-page-ends (:sections section-result)
                                                                  built-chunks)]
            (persist-extracted-data! ds {:run-id run-id
                                       :document-id document-id
                                       :campaign-id campaign-id
                                       :pdf-path pdf-path
                                       :content-hash content-hash
                                       :pages pages
                                       :blocks blocks
                                       :sections refined-sections
                                       :chunks built-chunks
                                       :reimport reimport})
            (complete-import! ds run-id campaign-id document-id pdf-path
                              pages blocks refined-sections built-chunks))))
      (catch Exception e
        (fail-import! ds run-id campaign-id document-id e)))))
