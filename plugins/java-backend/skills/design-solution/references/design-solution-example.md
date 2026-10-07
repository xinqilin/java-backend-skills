# Design Solution 完整範例

## Requirement

> I need an API for users to upload images. Images should be stored in S3, and users should be able to query all their uploaded images.

## Output (in Traditional Chinese)

## 需求理解

### 功能說明
建立圖片上傳功能，使用者可以上傳圖片到 S3，並提供查詢 API 列出該使用者所有上傳的圖片。

### 澄清問題
1. 圖片大小限制？建議限制 10MB
2. 允許的圖片格式？建議 JPG, PNG, GIF
3. 是否需要圖片縮圖功能？
4. 圖片存取權限？公開還是需要認證？

---

## 技術建議

### 建議方案
使用 Spring Boot + AWS S3 SDK，資料庫記錄圖片 metadata。

### 為什麼選擇這個方案
- S3 是成熟的物件儲存方案，成本低、可靠性高
- 不佔用應用伺服器儲存空間
- 支援 CDN 整合，可加速圖片載入

---

## 架構設計

### 系統架構
Controller → ImageService → S3Client + ImageRepository

### 資料模型
```java
@Entity
public class Image {
    private Long id;
    private Long userId;
    private String s3Key;
    private String fileName;
    private Long fileSize;
    private LocalDateTime createdAt;
}
```

### API 設計
- `POST /api/images` — 上傳圖片（multipart/form-data）
- `GET /api/images` — 列出當前使用者的圖片

---

## 實作 Todo List

### Phase 1: 基礎建設 (1 天)
- [ ] 新增 AWS S3 SDK 依賴 (`software.amazon.awssdk:s3`)
- [ ] 設定 S3 連線參數 (application.yml: `aws.s3.bucket`, `aws.region`)
- [ ] 建立 S3Client Bean

### Phase 2: 核心功能 (2 天)
- [ ] 建立 `Image` Entity (id, userId, s3Key, fileName, fileSize, createdAt)
- [ ] 建立 `ImageRepository extends JpaRepository<Image, Long>`
- [ ] 實作 `ImageService.upload(MultipartFile, Long userId)` — 上傳到 S3，存 metadata
- [ ] 實作 `ImageService.listByUser(Long userId)` — 查詢列表
- [ ] 建立 `ImageController` (POST /api/images, GET /api/images)
- [ ] 新增 `@ControllerAdvice` 處理 S3 和檔案大小例外

### Phase 3: 整合測試 (1 天)
- [ ] 撰寫 `ImageServiceTest` (mock S3Client)
- [ ] 撰寫 `ImageControllerTest` (@WebMvcTest)
- [ ] 手動測試完整流程

---

## 注意事項

### 潛在風險
1. **S3 連線失敗**：加入 retry 機制，回傳有意義的錯誤訊息

### 邊界情況
1. **檔案名稱含特殊字元**：上傳時產生 UUID 作為 S3 key
2. **重複上傳**：允許，用不同的 key 儲存

### 安全性考量
- 上傳前驗證 Content-Type（防止偽造）
- 設定合理的 `spring.servlet.multipart.max-file-size: 10MB`
- S3 bucket 設定適當的 ACL

---

## 預估工時

| 階段 | 預估時間 | 說明 |
|------|----------|------|
| Phase 1 | 0.5 天 | S3 設定 |
| Phase 2 | 2 天 | 核心功能 |
| Phase 3 | 1 天 | 測試 |
| **總計** | **3.5 天** | |
