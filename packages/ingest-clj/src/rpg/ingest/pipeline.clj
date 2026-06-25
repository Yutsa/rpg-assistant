(ns rpg.ingest.pipeline
  "Phase 0 import: extract PDFBox pages + blocks and persist to SQLite."
  (:require [clojure.string :as str]
            [next.jdbc :as jdbc]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.ids :as ids]
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

(defn- page-record [document-id page]
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
            :text-coverage-ratio 0.0
            :width (:width page)
            :height (:height page)}
     :blocks (mapv #(block-record document-id page-id page-number %) blocks)}))

(defn- build-page-records [document-id extracted]
  (let [per-page (mapv #(page-record document-id %) (:pages extracted))]
    {:pages (mapv :page per-page)
     :blocks (vec (mapcat :blocks per-page))}))

(defn- run-stats [pdf-path page-count block-count]
  {:page_count page-count
   :block_count block-count
   :source_pdf_path (.getAbsolutePath (java.io.File. pdf-path))
   :extraction_method "pdfbox"})

(defn- import-result [run-id campaign-id document-id status & {:keys [stats error-message]}]
  (cond-> {:ingestion-run-id run-id
           :campaign-id campaign-id
           :document-id document-id
           :status status}
    stats (assoc :stats stats)
    error-message (assoc :error-message error-message)))

(defn- persist-extracted-data!
  [ds {:keys [run-id document-id campaign-id pdf-path content-hash pages blocks reimport]}]
  (raw/upsert-document! ds document-id campaign-id
                        (.getName (java.io.File. pdf-path))
                        (count pages) content-hash)
  (raw/update-ingestion-run! ds run-id :document-id document-id)
  (when reimport
    (raw/delete-document-raw-data! ds document-id))
  (jdbc/with-transaction [tx ds]
    (raw/insert-pages! tx pages)
    (raw/insert-page-blocks! tx blocks)))

(defn- complete-import!
  [ds run-id campaign-id document-id pdf-path pages blocks]
  (let [stats (run-stats pdf-path (count pages) (count blocks))]
    (raw/update-ingestion-run! ds run-id :status "completed" :stats stats :finished true)
    (import-result run-id campaign-id document-id "completed" :stats stats)))

(defn- fail-import! [ds run-id campaign-id document-id exception]
  (raw/update-ingestion-run! ds run-id
                             :status "failed"
                             :error-message (.getMessage exception)
                             :finished true)
  (import-result run-id campaign-id document-id "failed"
                 :error-message (.getMessage exception)))

(defn import-pdf!
  "Import a PDF: pages + page_blocks only (phase 0). Returns result map."
  [{:keys [pdf-path campaign-id campaign-title game-system reimport db-spec]
    :or {reimport true}}]
  (let [run-id (ids/new-id "run")
        content-hash (ids/hash-file pdf-path)
        document-id (ids/document-id-from-hash content-hash)
        ds (db/connect :db-spec db-spec)]
    (raw/ensure-campaign! ds campaign-id :title campaign-title :game-system game-system)
    (raw/create-ingestion-run! ds {:id run-id
                                   :campaign-id campaign-id
                                   :status "running"})
    (try
      (let [extracted (pdf/extract-document pdf-path)
            {:keys [pages blocks]} (build-page-records document-id extracted)]
        (persist-extracted-data! ds {:run-id run-id
                                     :document-id document-id
                                     :campaign-id campaign-id
                                     :pdf-path pdf-path
                                     :content-hash content-hash
                                     :pages pages
                                     :blocks blocks
                                     :reimport reimport})
        (complete-import! ds run-id campaign-id document-id pdf-path pages blocks))
      (catch Exception e
        (fail-import! ds run-id campaign-id document-id e)))))
