import cv2

"""
NOTE:
This file is used to detect the label image within the macro image. 
However, it has not been utilized in this project. 
Perhaps it could be beneficial for future works.
"""

for i in range(1, 8):
    image = cv2.imread('./data/label/Picture'+str(i)+'.png')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape

    """
        Removes part of the border inside the macro image.
        ( Because as a review, there are some macro images when taken at a distance, 
        there will often be an outer border, which makes it difficult to find the label.)
    """
    cv2.rectangle(gray, pt1=(0, 0), pt2=(width, height), color=(255, 255, 255), thickness=60)

    # use Thresholding to replace pixels with values greater than 0 to 255.
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)[1]

    # exchange black and white pixels together to apply Morphological Transformations: Erosion, Dilation and Closing
    # more info: https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
    thresh = cv2.subtract(255, thresh)

    # use Erosion to remove small white noises
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    erosion = cv2.erode(thresh, kernel, iterations=1)

    # after removing small white noises, using Dilation to create connected objects
    # e.g. some texts can connect together and they become a white block
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    dilate = cv2.dilate(erosion, kernel, iterations=3)

    # using Closing to close small black holes inside the foreground objects
    morpho = cv2.morphologyEx(dilate, cv2.MORPH_CLOSE, kernel)

    # find contour of label image
    contours, hierarchy = cv2.findContours(image=morpho, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_NONE)
    image_copy = image.copy()
    left_contour = contours[0]
    l_x, _, l_w, _ = cv2.boundingRect(left_contour)

    for contour in contours:
        # find bounding rectangles
        x, y, w, h = cv2.boundingRect(contour)

        #
        if l_x > x:
            l_x, l_w = x, w
            left_contour = contour
            continue

    # get label image
    image_copy = image_copy[0:height, 0:l_w + 6]

    cv2.imshow('1_image_' + str(i), image)
    cv2.imshow('2_gray_' + str(i), gray)
    cv2.imshow('3_thresh_'+str(i), thresh)
    cv2.imshow('4_erosion' + str(i), erosion)
    cv2.imshow('5_dilate'+str(i), dilate)
    cv2.imshow('6_morpho' + str(i), morpho)
    cv2.imshow("7_bboxes_img" + str(i), image_copy)

cv2.waitKey()
