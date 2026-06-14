(ns rpg-assistant-web.router-test
  (:require [cljs.test :refer [deftest is]]
            [rpg-assistant-web.router :as router]))

(deftest url->location-campaigns
  (is (= :pages/campaigns
         (:location/page-id (router/url->location router/routes "/")))))

(deftest url->location-document-explorer
  (let [loc (router/url->location router/routes "/documents/doc_1?section=sec_1")]
    (is (= :pages/document-explorer (:location/page-id loc)))
    (is (= "doc_1" (get-in loc [:location/params :document-id])))
    (is (= "sec_1" (or (get-in loc [:location/query-params "section"])
                       (get-in loc [:location/query-params :section]))))))

(deftest location->url-roundtrip
  (let [loc {:location/page-id :pages/document-chunk
             :location/params {:document-id "doc_1" :chunk-id "chunk_1"}
             :location/query-params {"section" "sec_1"}}]
    (is (= "/documents/doc_1/chunks/chunk_1?section=sec_1"
           (router/location->url router/routes loc)))))

(deftest essentially-same-ignores-hash
  (let [base {:location/page-id :pages/document-explorer
              :location/params {:document-id "doc_1"}
              :location/query-params {"section" "sec_1"}}
        with-hash (assoc base :location/hash-params {"menu" "1"})]
    (is (router/essentially-same? base with-hash))))
