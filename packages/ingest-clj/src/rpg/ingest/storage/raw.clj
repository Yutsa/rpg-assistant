(ns rpg.ingest.storage.raw
  (:require [clojure.string :as str]
            [next.jdbc :as jdbc]
            [next.jdbc.result-set :as rs]
            [rpg.ingest.storage.json-util :as json-util])
  (:import [java.time Instant]))

(defn- utc-now []
  (str (Instant/now)))

(defn ensure-campaign!
  [ds campaign-id & {:keys [title game-system]}]
  (jdbc/execute! ds
                 ["INSERT INTO campaigns (id, title, game_system)
                   VALUES (?, ?, ?)
                   ON CONFLICT (id) DO NOTHING"
                  campaign-id (or title campaign-id) (or game-system "")]))

(defn upsert-document!
  [ds document-id campaign-id filename page-count content-hash]
  (jdbc/execute! ds
                 ["INSERT INTO documents (id, campaign_id, filename, page_count, content_hash)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET
                     filename = excluded.filename,
                     page_count = excluded.page_count,
                     content_hash = excluded.content_hash"
                  document-id campaign-id filename page-count content-hash]))

(defn create-ingestion-run!
  [ds {:keys [id campaign-id document-id stage status error-message stats started-at]}]
  (jdbc/execute! ds
                 ["INSERT INTO ingestion_runs
                     (id, campaign_id, document_id, stage, status, error_message, stats, started_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                  id campaign-id document-id (or stage "raw") (or status "pending")
                  error-message (json-util/encode-json (or stats {}))
                  (or started-at (utc-now))]))

(defn update-ingestion-run!
  [ds run-id & {:keys [status document-id error-message stats finished]}]
  (let [fields (cond-> []
                 status (conj "status = ?")
                 document-id (conj "document_id = ?")
                 error-message (conj "error_message = ?")
                 stats (conj "stats = ?")
                 finished (conj "finished_at = ?"))
        params (cond-> []
                 status (conj status)
                 document-id (conj document-id)
                 error-message (conj error-message)
                 stats (conj (json-util/encode-json stats))
                 finished (conj (utc-now)))]
    (when (seq fields)
      (jdbc/execute! ds
                     (into [(str "UPDATE ingestion_runs SET "
                                 (str/join ", " fields)
                                 " WHERE id = ?")]
                           (conj params run-id))))))

(defn delete-document-raw-data!
  [ds document-id]
  (doseq [table ["chunks" "sections" "page_blocks" "pages"]]
    (jdbc/execute! ds [(str "DELETE FROM " table " WHERE document_id = ?") document-id])))

(defn insert-pages!
  [ds pages]
  (doseq [page pages]
    (jdbc/execute! ds
                   ["INSERT INTO pages
                       (id, document_id, page_number, text, extraction_method,
                        has_text, text_coverage_ratio, width, height)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (document_id, page_number) DO UPDATE SET
                       text = excluded.text,
                       extraction_method = excluded.extraction_method,
                       has_text = excluded.has_text,
                       text_coverage_ratio = excluded.text_coverage_ratio,
                       width = excluded.width,
                       height = excluded.height"
                    (:id page)
                    (:document-id page)
                    (:page-number page)
                    (:text page)
                    (:extraction-method page)
                    (if (:has-text page) 1 0)
                    (or (:text-coverage-ratio page) 0.0)
                    (:width page)
                    (:height page)])))

(defn insert-page-blocks!
  [ds blocks]
  (doseq [block blocks]
    (jdbc/execute! ds
                   ["INSERT INTO page_blocks
                       (id, document_id, page_id, page_number, block_index, text,
                        bbox_json, metadata_json)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (id) DO UPDATE SET
                       document_id = excluded.document_id,
                       page_id = excluded.page_id,
                       page_number = excluded.page_number,
                       block_index = excluded.block_index,
                       text = excluded.text,
                       bbox_json = excluded.bbox_json,
                       metadata_json = excluded.metadata_json"
                    (:id block)
                    (:document-id block)
                    (:page-id block)
                    (:page-number block)
                    (:block-index block)
                    (:text block)
                    (json-util/encode-json (:bbox block))
                    (json-util/encode-json (:metadata block))])))

(defn count-rows
  [ds table document-id]
  (-> (jdbc/execute-one! ds
                         [(str "SELECT COUNT(*) AS count FROM " table " WHERE document_id = ?")
                          document-id]
                         {:builder-fn rs/as-unqualified-maps})
      :count))

(defn get-ingestion-run
  [ds run-id]
  (when-let [row (jdbc/execute-one! ds
                                    ["SELECT id, campaign_id, document_id, stage, status,
                                            error_message, stats, started_at, finished_at
                                     FROM ingestion_runs WHERE id = ?"
                                     run-id]
                                    {:builder-fn rs/as-unqualified-maps})]
    (update row :stats json-util/decode-json)))

(defn get-document
  [ds document-id]
  (jdbc/execute-one! ds
                     ["SELECT id, campaign_id, filename, page_count, content_hash
                      FROM documents WHERE id = ?"
                      document-id]
                     {:builder-fn rs/as-unqualified-maps}))

(defn campaign-exists?
  [ds campaign-id]
  (boolean
   (jdbc/execute-one! ds
                      ["SELECT 1 AS ok FROM campaigns WHERE id = ?"
                       campaign-id]
                      {:builder-fn rs/as-unqualified-maps})))
