-- ============================================================
-- PROJECT 16: SPORTS TICKETING MANAGEMENT SYSTEM
-- Database Schema - MySQL
-- DATCOM Lab - NEU College of Technology
-- ============================================================

DROP DATABASE sports_ticketing;
CREATE DATABASE sports_ticketing;
USE sports_ticketing;

-- ============================================================
-- 1. BẢNG EVENTS (Sự kiện thể thao)
-- ============================================================
CREATE TABLE Events (
    EventID     INT AUTO_INCREMENT PRIMARY KEY,
    EventName   VARCHAR(150)    NOT NULL,
    EventDate   DATETIME        NOT NULL,
    Venue       VARCHAR(200)    NOT NULL,
    Sport       VARCHAR(50)     NOT NULL,           -- loại môn thể thao
    Status      ENUM('Upcoming','Ongoing','Finished','Cancelled') DEFAULT 'Upcoming',
    CreatedAt   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. BẢNG BOXOFFICES (Quầy bán vé)
-- ============================================================
CREATE TABLE BoxOffices (
    BoxOfficeID INT AUTO_INCREMENT PRIMARY KEY,
    OfficeName  VARCHAR(100)    NOT NULL,
    Address     VARCHAR(200)    NOT NULL,
    Phone       VARCHAR(20),
    Email       VARCHAR(100),
    CreatedAt   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 3. BẢNG CUSTOMERS (Khách hàng)
-- ============================================================
CREATE TABLE Customers (
    CustomerID      INT AUTO_INCREMENT PRIMARY KEY,
    CustomerName    VARCHAR(100)    NOT NULL,
    PhoneNumber     VARCHAR(20)     NOT NULL UNIQUE,
    Address         VARCHAR(200),
    Email           VARCHAR(100)    UNIQUE,
    -- Mã hóa thông tin nhạy cảm (AES_ENCRYPT khi INSERT)
    PasswordHash    VARCHAR(255),
    CreatedAt       TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 4. BẢNG SEATS (Ghế ngồi)
-- ============================================================
CREATE TABLE Seats (
    SeatID      INT AUTO_INCREMENT PRIMARY KEY,
    EventID     INT             NOT NULL,
    SeatNumber  VARCHAR(10)     NOT NULL,
    SeatType    ENUM('VIP','Standard','Economy') NOT NULL,
    Status      ENUM('Available','Booked','Reserved','Unavailable') DEFAULT 'Available',
    CONSTRAINT fk_seat_event FOREIGN KEY (EventID) REFERENCES Events(EventID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY uq_seat_event (EventID, SeatNumber)  -- mỗi ghế là duy nhất trong 1 sự kiện
);

-- ============================================================
-- 5. BẢNG TICKETS (Vé)
-- ============================================================
CREATE TABLE Tickets (
    TicketID        INT AUTO_INCREMENT PRIMARY KEY,
    EventID         INT             NOT NULL,
    SeatID          INT             NOT NULL,
    CustomerID      INT             NOT NULL,
    BoxOfficeID     INT             NOT NULL,
    TicketType      ENUM('VIP','Standard','Economy') NOT NULL,
    Price           DECIMAL(10,2)   NOT NULL CHECK (Price >= 0),
    Status          ENUM('Active','Cancelled','Used') DEFAULT 'Active',
    PurchaseDate    DATETIME        DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ticket_event      FOREIGN KEY (EventID)     REFERENCES Events(EventID),
    CONSTRAINT fk_ticket_seat       FOREIGN KEY (SeatID)      REFERENCES Seats(SeatID),
    CONSTRAINT fk_ticket_customer   FOREIGN KEY (CustomerID)  REFERENCES Customers(CustomerID),
    CONSTRAINT fk_ticket_boxoffice  FOREIGN KEY (BoxOfficeID) REFERENCES BoxOffices(BoxOfficeID)
);

-- ============================================================
-- INDEXES (Tăng tốc truy vấn)
-- ============================================================
CREATE INDEX idx_tickets_event      ON Tickets(EventID);
CREATE INDEX idx_tickets_customer   ON Tickets(CustomerID);
CREATE INDEX idx_tickets_status     ON Tickets(Status);
CREATE INDEX idx_seats_event_status ON Seats(EventID, Status);
CREATE INDEX idx_events_date        ON Events(EventDate);

-- ============================================================
-- VIEWS
-- ============================================================

-- View 1: Sự kiện đã hết vé
CREATE VIEW vw_soldout_events AS
SELECT e.EventID, e.EventName, e.EventDate, e.Venue,
       COUNT(s.SeatID) AS TotalSeats,
       SUM(CASE WHEN s.Status = 'Booked' THEN 1 ELSE 0 END) AS BookedSeats
FROM Events e
JOIN Seats s ON e.EventID = s.EventID
GROUP BY e.EventID
HAVING TotalSeats = BookedSeats;

-- View 2: Doanh thu theo sự kiện
CREATE VIEW vw_revenue_by_event AS
SELECT e.EventID, e.EventName, e.EventDate, e.Venue,
       COUNT(t.TicketID)   AS TotalTicketsSold,
       SUM(t.Price)        AS TotalRevenue,
       AVG(t.Price)        AS AvgTicketPrice
FROM Events e
LEFT JOIN Tickets t ON e.EventID = t.EventID AND t.Status = 'Active'
GROUP BY e.EventID;

-- View 3: Ghế còn trống theo sự kiện
CREATE VIEW vw_available_seats AS
SELECT e.EventID, e.EventName, e.EventDate,
       s.SeatID, s.SeatNumber, s.SeatType
FROM Seats s
JOIN Events e ON s.EventID = e.EventID
WHERE s.Status = 'Available';

-- View 4: Lịch sử mua vé của khách hàng
CREATE VIEW vw_customer_purchase_history AS
SELECT c.CustomerID, c.CustomerName, c.PhoneNumber,
       t.TicketID, t.PurchaseDate, t.Price, t.Status AS TicketStatus,
       e.EventName, e.EventDate, e.Venue,
       s.SeatNumber, s.SeatType,
       b.OfficeName
FROM Tickets t
JOIN Customers  c ON t.CustomerID   = c.CustomerID
JOIN Events     e ON t.EventID      = e.EventID
JOIN Seats      s ON t.SeatID       = s.SeatID
JOIN BoxOffices b ON t.BoxOfficeID  = b.BoxOfficeID;

-- ============================================================
-- STORED PROCEDURES
-- ============================================================

DELIMITER $$

-- Procedure 1: Đặt vé
CREATE PROCEDURE sp_book_ticket(
    IN p_EventID     INT,
    IN p_SeatID      INT,
    IN p_CustomerID  INT,
    IN p_BoxOfficeID INT,
    IN p_TicketType  VARCHAR(20),
    IN p_Price       DECIMAL(10,2),
    OUT p_TicketID   INT,
    OUT p_Message    VARCHAR(100)
)
BEGIN
    DECLARE v_SeatStatus VARCHAR(20);

    START TRANSACTION;

    -- Kiểm tra ghế còn trống không (lock để tránh race condition)
    SELECT Status INTO v_SeatStatus
    FROM Seats WHERE SeatID = p_SeatID FOR UPDATE;

    IF v_SeatStatus != 'Available' THEN
        SET p_TicketID = 0;
        SET p_Message = 'Ghế đã được đặt hoặc không khả dụng.';
        ROLLBACK;
    ELSE
        -- Tạo vé
        INSERT INTO Tickets (EventID, SeatID, CustomerID, BoxOfficeID, TicketType, Price)
        VALUES (p_EventID, p_SeatID, p_CustomerID, p_BoxOfficeID, p_TicketType, p_Price);

        SET p_TicketID = LAST_INSERT_ID();

        -- Cập nhật trạng thái ghế
        UPDATE Seats SET Status = 'Booked' WHERE SeatID = p_SeatID;

        SET p_Message = 'Đặt vé thành công.';
        COMMIT;
    END IF;
END$$

-- Procedure 2: Hủy vé
CREATE PROCEDURE sp_cancel_ticket(
    IN  p_TicketID INT,
    OUT p_Message  VARCHAR(100)
)
BEGIN
    DECLARE v_SeatID INT;
    DECLARE v_Status VARCHAR(20);

    SELECT SeatID, Status INTO v_SeatID, v_Status
    FROM Tickets WHERE TicketID = p_TicketID;

    IF v_Status = 'Cancelled' THEN
        SET p_Message = 'Vé đã bị hủy trước đó.';
    ELSE
        START TRANSACTION;
        UPDATE Tickets SET Status = 'Cancelled' WHERE TicketID = p_TicketID;
        UPDATE Seats   SET Status = 'Available' WHERE SeatID   = v_SeatID;
        COMMIT;
        SET p_Message = 'Hủy vé thành công.';
    END IF;
END$$

-- Procedure 3: Báo cáo doanh thu theo khoảng thời gian
CREATE PROCEDURE sp_revenue_report(
    IN p_StartDate DATE,
    IN p_EndDate   DATE
)
BEGIN
    SELECT e.EventName, e.EventDate,
           COUNT(t.TicketID) AS TicketsSold,
           SUM(t.Price)      AS Revenue
    FROM Tickets t
    JOIN Events e ON t.EventID = e.EventID
    WHERE t.Status = 'Active'
      AND DATE(t.PurchaseDate) BETWEEN p_StartDate AND p_EndDate
    GROUP BY e.EventID
    ORDER BY Revenue DESC;
END$$

DELIMITER ;

-- ============================================================
-- USER DEFINED FUNCTIONS
-- ============================================================

DELIMITER $$

-- Function 1: Tổng doanh thu theo sự kiện
CREATE FUNCTION fn_total_revenue(p_EventID INT)
RETURNS DECIMAL(12,2)
DETERMINISTIC
BEGIN
    DECLARE v_Total DECIMAL(12,2);
    SELECT COALESCE(SUM(Price), 0) INTO v_Total
    FROM Tickets
    WHERE EventID = p_EventID AND Status = 'Active';
    RETURN v_Total;
END$$

-- Function 2: Tổng vé đã bán theo sự kiện
CREATE FUNCTION fn_tickets_sold(p_EventID INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE v_Count INT;
    SELECT COUNT(*) INTO v_Count
    FROM Tickets
    WHERE EventID = p_EventID AND Status = 'Active';
    RETURN v_Count;
END$$

-- Function 3: Số ghế còn trống theo sự kiện
CREATE FUNCTION fn_available_seats(p_EventID INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE v_Count INT;
    SELECT COUNT(*) INTO v_Count
    FROM Seats
    WHERE EventID = p_EventID AND Status = 'Available';
    RETURN v_Count;
END$$

DELIMITER ;

-- ============================================================
-- TRIGGERS
-- ============================================================

DELIMITER $$

-- Trigger 1: Khi vé bị hủy → trả ghế về Available
CREATE TRIGGER trg_after_ticket_cancel
AFTER UPDATE ON Tickets
FOR EACH ROW
BEGIN
    IF NEW.Status = 'Cancelled' AND OLD.Status != 'Cancelled' THEN
        UPDATE Seats SET Status = 'Available' WHERE SeatID = NEW.SeatID;
    END IF;
END$$

-- Trigger 2: Khi vé được tạo → đặt ghế thành Booked
CREATE TRIGGER trg_after_ticket_insert
AFTER INSERT ON Tickets
FOR EACH ROW
BEGIN
    UPDATE Seats SET Status = 'Booked' WHERE SeatID = NEW.SeatID;
END$$

-- Trigger 3: Không cho xóa vé Active (bảo vệ dữ liệu)
CREATE TRIGGER trg_before_ticket_delete
BEFORE DELETE ON Tickets
FOR EACH ROW
BEGIN
    IF OLD.Status = 'Active' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Không thể xóa vé đang Active. Hãy hủy vé trước.';
    END IF;
END$$

DELIMITER ;

-- ============================================================
-- USER ROLES & SECURITY
-- ============================================================

-- Tạo user roles
CREATE USER IF NOT EXISTS 'cashier'@'localhost'   IDENTIFIED BY 'cashier_pass_2024';
CREATE USER IF NOT EXISTS 'manager'@'localhost'   IDENTIFIED BY 'manager_pass_2024';
CREATE USER IF NOT EXISTS 'admin_user'@'localhost' IDENTIFIED BY 'admin_pass_2024';

-- Cashier: chỉ được đọc/ghi vé và khách hàng
GRANT SELECT, INSERT ON sports_ticketing.Tickets   TO 'cashier'@'localhost';
GRANT SELECT, INSERT ON sports_ticketing.Customers TO 'cashier'@'localhost';
GRANT SELECT          ON sports_ticketing.Events    TO 'cashier'@'localhost';
GRANT SELECT          ON sports_ticketing.Seats     TO 'cashier'@'localhost';
GRANT EXECUTE         ON PROCEDURE sports_ticketing.sp_book_ticket   TO 'cashier'@'localhost';
GRANT EXECUTE         ON PROCEDURE sports_ticketing.sp_cancel_ticket TO 'cashier'@'localhost';

-- Manager: đọc tất cả + xem báo cáo
GRANT SELECT ON sports_ticketing.* TO 'manager'@'localhost';
GRANT EXECUTE ON PROCEDURE sports_ticketing.sp_revenue_report TO 'manager'@'localhost';

-- Admin: toàn quyền
GRANT ALL PRIVILEGES ON sports_ticketing.* TO 'admin_user'@'localhost';

FLUSH PRIVILEGES;

-- ============================================================
-- SAMPLE DATA 
-- ============================================================
INSERT INTO Events (EventName, EventDate, Venue, Sport, Status) VALUES
('Chung kết V.League 2024',        '2024-12-15 19:00:00', 'Sân Mỹ Đình, Hà Nội',       'Bóng đá',    'Upcoming'),
('SEA Games Bóng rổ Nam',          '2024-11-20 15:00:00', 'Nhà thi đấu Phú Thọ, TP.HCM','Bóng rổ',   'Upcoming'),
('Giải cầu lông toàn quốc 2024',   '2024-11-05 08:00:00', 'Cung thể thao Hà Nội',       'Cầu lông',   'Finished'),
('Cup bóng chuyền nữ quốc tế',     '2024-12-01 14:00:00', 'Cung thể thao Tinh Võ',      'Bóng chuyền','Upcoming'),
('Giải marathon Hà Nội 2024',      '2024-10-28 05:30:00', 'Hồ Hoàn Kiếm, Hà Nội',      'Điền kinh',  'Finished');

INSERT INTO BoxOffices (OfficeName, Address, Phone, Email) VALUES
('Quầy vé Mỹ Đình',    'đường Lê Đức Thọ, Mỹ Đình, Hà Nội',    '024-3834-5678', 'mydinhticket@sport.vn'),
('Quầy vé Phú Thọ',    '1 Lữ Gia, Phường 15, Q.11, TP.HCM',     '028-3865-2233', 'phutho@sport.vn'),
('Quầy vé Online HN',  'Hà Nội (online)',                          '1900-1234',     'online.hn@sport.vn'),
('Quầy vé Cung TT HN', 'Trần Phú, Hà Đông, Hà Nội',              '024-3333-4444', 'cungtt@sport.vn');

INSERT INTO Customers (CustomerName, PhoneNumber, Address, Email) VALUES
('Nguyễn Văn An',    '0912345678', '12 Lý Thường Kiệt, Hoàn Kiếm, HN', 'an.nguyen@email.com'),
('Trần Thị Bích',    '0987654321', '45 Nguyễn Trãi, Q.1, TP.HCM',       'bich.tran@email.com'),
('Lê Minh Châu',     '0978123456', '88 Bà Triệu, Hai Bà Trưng, HN',     'chau.le@email.com'),
('Phạm Quốc Dũng',   '0965432187', '23 Điện Biên Phủ, Đà Nẵng',         'dung.pham@email.com'),
('Hoàng Thị Lan',    '0934567812', '67 Trần Hưng Đạo, Hoàn Kiếm, HN',  'lan.hoang@email.com');

INSERT INTO Seats (EventID, SeatNumber, SeatType, Status) VALUES
(1, 'A01', 'VIP',      'Available'),
(1, 'A02', 'VIP',      'Available'),
(1, 'B01', 'Standard', 'Available'),
(1, 'B02', 'Standard', 'Available'),
(1, 'C01', 'Economy',  'Available'),
(2, 'A01', 'VIP',      'Available'),
(2, 'B01', 'Standard', 'Available'),
(2, 'C01', 'Economy',  'Available');
