(ns rpg-assistant-web.router-test
  (:require
   [cljs.test :refer-macros [deftest is testing]]
   [rpg-assistant-web.router :as router]))

(deftest url-roundtrip-test
  (testing "campaign documents"
    (let [loc {:location/page-id :pages/campaign-documents
               :location/params {:campaign-id "momie"}}
          url (router/location->url router/routes loc)]
      (is (= "/campaigns/momie" url))
      (is (= loc (router/url->location router/routes url)))
      (is (= loc (router/url->location router/routes (str "http://127.0.0.1:5174" url))))))

  (testing "campaign list root"
    (let [loc {:location/page-id :pages/campaigns}
          url (router/location->url router/routes loc)]
      (is (= "/" url))
      (is (= :pages/campaigns
             (:location/page-id (router/url->location router/routes "/"))))
      (is (= :pages/campaigns
             (:location/page-id (router/url->location router/routes url))))))

  (testing "document explorer"
    (let [loc {:location/page-id :pages/document-explorer
               :location/params {:document-id "doc_010672301b36"}}
          url (router/location->url router/routes loc)]
      (is (= "/documents/doc_010672301b36" url))
      (is (= loc (router/url->location router/routes url)))))

  (testing "stat block detail with encoded name"
    (let [loc {:location/page-id :pages/stat-block-detail
               :location/params {:document-id "doc_1"
                                 :stat-block-name "Momie ancienne"}}
          url (router/location->url router/routes loc)]
      (is (string? url))
      (is (= loc (router/url->location router/routes url)))))

  (testing "index.html boot path"
    (is (= :pages/campaigns
           (:location/page-id (router/url->location router/routes "/index.html")))))

  (testing "unknown path"
    (is (nil? (router/url->location router/routes "/unknown")))
    (is (nil? (:location/page-id (router/current-location-for-path "/unknown"))))
    (is (nil? (router/url->location router/routes "/documents/doc_1/typo"))))

  (testing "trailing slash paths"
    (is (= :pages/campaign-documents
           (:location/page-id (router/url->location router/routes "/campaigns/momie/"))))))
